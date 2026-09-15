"""Polling and item effects, testable with an in-memory Dolphin substitute."""
from ..Items import (BARKER_COIN, COIN_BUNDLE_DATA, COIN_TRAP_DATA, GOAL_WORLD_ACCESS,
                     ITEM_TABLE, PAR_CLUB_PIECES, UNLOCKS)
from ..Locations import LOCATION_TABLE
from ..data import MINIGAMES
from .constants import RESULT_VTABLE, ROOT_LOCKS, ROOT_SUB, SHOP_MANAGER_STATE
from .memory import MemoryUnavailable, valid_pointer

ID_TO_NAME = {code: name for name, code in ITEM_TABLE.items()}
VTABLE_TO_WORLD = {vtable: i for i, (_, vtable) in enumerate(MINIGAMES)}


def validate_slot(data):
    if data.get('schema_version') != 5:
        raise ValueError("Unsupported Carnival Games MiniGolf slot-data version")
    start, final = data.get('starting_world'), data.get('goal_world')
    if type(start) is not int or not 0 <= start < 9:
        raise ValueError("Invalid starting world")
    if final is not None and (type(final) is not int or not 0 <= final < 9 or final == start):
        raise ValueError("Invalid goal world")
    goal = data.get('goal')
    if type(goal) is not int or not 0 <= goal <= 2:
        raise ValueError("Invalid goal")
    if (goal == 1) != (final is not None):
        raise ValueError("Goal World must be configured exactly for the Goal World goal")
    if type(data.get('counter_mode')) is not bool:
        raise ValueError("Invalid Barker mode")
    access = data.get('goal_world_access')
    if type(access) is not int or not 0 <= access <= 1:
        raise ValueError("Invalid Goal World Access")
    expected_counter = goal == 2 or (goal == 1 and access == 1)
    if data['counter_mode'] != expected_counter:
        raise ValueError("Invalid Barker counter mode")
    required = data.get('required_coins')
    if type(required) is not int or not (1 <= required <= 50 if data['counter_mode'] else required == 0):
        raise ValueError("Invalid Barker requirement")
    total = data.get('total_barker_coins')
    if type(total) is not int or total != (required * 3 + 1) // 2:
        raise ValueError("Invalid Barker Coin pool size")
    if not isinstance(data.get('locations'), dict):
        raise ValueError("Missing MiniGolf location data")
    for name, value in data['locations'].items():
        if name not in LOCATION_TABLE or value.get('code') != LOCATION_TABLE[name].code:
            raise ValueError("Unknown MiniGolf location mapping")
        if data['counter_mode'] and LOCATION_TABLE[name].kind == 'barker_shop':
            raise ValueError("Barker Shop is incompatible with counter goals")
    if not all(name in data['locations'] for name, d in LOCATION_TABLE.items() if d.kind == 'par'):
        raise ValueError("Slot is missing mandatory par checks")
    if not all(name in data['locations'] for name, d in LOCATION_TABLE.items() if d.kind == 'complete'):
        raise ValueError("Slot is missing mandatory hole completion checks")


class Runtime:
    def __init__(self, slot_data, journal):
        validate_slot(slot_data)
        self.slot = slot_data
        self.journal = journal
        self.locations = {name: LOCATION_TABLE[name] for name in slot_data['locations']}
        self.lookup = {(d.kind, d.index): d.code for d in self.locations.values()}
        self.previous_hole = None
        self.previous_goal = None
        self.result_context = None
        self.previous_results = set()
        self.active_minigame = None
        self.previous_manager_state = None
        self.latched_hole = None
        self.pieces_projected = False

    def reset_transient(self):
        self.previous_hole = None
        self.previous_goal = None
        self.result_context = None
        self.previous_results.clear()
        self.active_minigame = None
        self.previous_manager_state = None
        self.latched_hole = None

    def unlocked(self, items):
        names = [ID_TO_NAME.get(item) for item in items]
        coins = names.count(BARKER_COIN)
        unlocked = {self.slot['starting_world']}
        unlocked.update(i for i, name in enumerate(UNLOCKS) if name in names and i != self.slot['goal_world'])
        if self.slot['goal_world'] is not None and GOAL_WORLD_ACCESS in names:
            unlocked.add(self.slot['goal_world'])
        return unlocked, coins

    def poll(self, memory, items, local_player=0, history_ready=True):
        if not memory.verify_game():
            self.reset_transient()
            raise MemoryUnavailable("Waiting for supported Carnival Games MiniGolf (RG9P54, verified revision)")
        cursor = self.journal.data['cursor']
        if history_ready and cursor > len(items):
            raise MemoryUnavailable("Waiting for complete AP received-item history")
        if any(item not in ID_TO_NAME for item in items):
            raise ValueError("Unknown received MiniGolf item ID; update the client")
        snapshot = memory.resolve(local_player)
        root, sub = snapshot.root, snapshot.root + ROOT_SUB
        # Only the configured AP profile may contribute locations. Other valid
        # local roots can contain stale or unrelated save progress.
        persistent = memory.read(sub, 0xA2)
        manager_state = memory.integer(snapshot.manager + 0xBC)
        unlocked, coins = self.unlocked(items)
        checks = set()
        for data in self.locations.values():
            offset = {'barker': 0x6A, 'shop': 0, 'club': 0, 'secret': 0, 'barker_shop': 0}.get(data.kind)
            if offset is not None and persistent[offset + data.index] == 1:
                checks.add(data.code)
        if manager_state != SHOP_MANAGER_STATE and not self.pieces_projected:
            for hole, value in enumerate(persistent[0x86:0xA1]):
                if value == 1:
                    checks.add(self.lookup['par', hole])
        hole_def = memory.integer(snapshot.manager + 0x10C)
        derived_hole = self.derive_hole_id(memory, hole_def)
        if manager_state == 5 and derived_hole is not None:
            self.latched_hole = (snapshot.root, derived_hole, hole_def)
        if self.previous_manager_state == 5 and manager_state == 6 and self.latched_hole is not None:
            latched_root, hole, latched_def = self.latched_hole
            if latched_root == snapshot.root:
                self.add_hole_completion(memory, snapshot.root, latched_def, hole, checks)
        self.previous_manager_state = manager_state
        try:
            active_gameplay = self.read_transient(memory, snapshot, checks, derived_hole, hole_def, manager_state)
        except MemoryUnavailable:
            # A single failed MEM2 live-object read must not block persistent
            # roots, locations, locks, or receive-once item processing.
            active_gameplay = True
        if (history_ready and self.slot['goal_world_access'] == 1
                and coins >= self.slot['required_coins']):
            requirement = next((d.code for d in self.locations.values() if d.kind == 'barker_requirement'), None)
            if requirement is not None:
                checks.add(requirement)
        self.journal.add_checks(checks)
        memory.confirm(snapshot)
        locks = bytes(0 if i in unlocked else 1 for i in range(9))
        for player_root in snapshot.roots:
            if memory.read(player_root + ROOT_LOCKS, 9) != locks:
                memory.write(player_root + ROOT_LOCKS, locks)
                memory.put(player_root + ROOT_SUB + 0xA1, 1)
        if history_ready:
            for index in range(cursor, len(items)):
                memory.confirm(snapshot)
                name = ID_TO_NAME.get(items[index])
                if name is None:
                    raise ValueError(f"Unknown received MiniGolf item ID: {items[index]}")
                if name in COIN_BUNDLE_DATA:
                    world, amount = COIN_BUNDLE_DATA[name]
                    self.journal.grant(memory, sub, index, 0x58 + 2*world, amount, 2)
                elif name in COIN_TRAP_DATA:
                    world, amount = COIN_TRAP_DATA[name]
                    self.journal.grant(memory, sub, index, 0x58 + 2*world, -amount, 2)
                elif name == BARKER_COIN and not self.slot['counter_mode']:
                    self.journal.grant(memory, sub, index, 0x85, 1, 1)
                else:
                    self.journal.advance(index)
        if (history_ready and self.slot['counter_mode']
                and memory.integer(sub + 0x85, 1) != min(coins, 255)):
            memory.put(sub + 0x85, min(coins, 255))
            memory.put(sub + 0xA1, 1)
        received_names = [ID_TO_NAME[item] for item in items]
        shop_context = history_ready and manager_state == SHOP_MANAGER_STATE
        pieces = bytes(int(shop_context and piece < min(3, received_names.count(name)))
                       for name in PAR_CLUB_PIECES for piece in range(3))
        if memory.read(sub + 0x86, 27) != pieces:
            memory.write(sub + 0x86, pieces)
            if not shop_context:
                memory.put(sub + 0xA1, 1)
        self.pieces_projected = shop_context and any(pieces)
        return set(self.journal.data['checks']) & {d.code for d in self.locations.values()}

    @staticmethod
    def is_shop_context(memory, snapshot, active_gameplay):
        """Independent Pro Shop dumps identify manager state 3 as the shop."""
        return memory.integer(snapshot.manager + 0xBC) == SHOP_MANAGER_STATE

    def clear_piece_projection(self, memory, local_player=0):
        if not self.pieces_projected or not memory.verify_game():
            return
        snapshot = memory.resolve(local_player)
        memory.write(snapshot.root + ROOT_SUB + 0x86, bytes(27))
        memory.put(snapshot.root + ROOT_SUB + 0xA1, 1)
        self.pieces_projected = False

    @staticmethod
    def valid_hole_definition(memory, address):
        if not valid_pointer(address, 0x10):
            return False
        return (all(valid_pointer(memory.integer(address + offset), 4) for offset in (0, 4, 8))
                and 1 <= memory.integer(address + 0x0C) <= 20)

    @classmethod
    def derive_hole_id(cls, memory, current):
        try:
            if not cls.valid_hole_definition(memory, current):
                return None
            index = 0
            while index < 26 and cls.valid_hole_definition(memory, current - 0x10):
                current -= 0x10
                index += 1
            return index
        except MemoryUnavailable:
            return None

    def add_hole_completion(self, memory, root, hole_def, hole, checks):
        strokes = memory.integer(root + 0x2DC)
        par = memory.integer(hole_def + 0x0C)
        checks.add(self.lookup['complete', hole])
        if 1 <= strokes <= par <= 20:
            checks.add(self.lookup['par', hole])
        if strokes == 1 and ('hio', hole) in self.lookup:
            checks.add(self.lookup['hio', hole])

    def read_transient(self, memory, snapshot, checks, derived_hole, hole_def, manager_state):
        session = snapshot.session
        if session is None:
            self.reset_transient()
            return False
        controller = memory.integer(session + 0xFC)
        vtable = memory.integer(controller + 0x1C) if valid_pointer(controller, 0x134) else None
        minigame = VTABLE_TO_WORLD.get(vtable)
        if minigame is not None:
            self.previous_hole = self.previous_goal = None
            if self.active_minigame != minigame:
                self.active_minigame = minigame
                self.result_context = None
                self.previous_results.clear()
        if self.active_minigame is not None:
            context = (snapshot.root, self.active_minigame)
            array = memory.integer(snapshot.manager + 0x100)
            count = memory.integer(snapshot.manager + 0x104)
            if count > 4096 or not valid_pointer(array, max(4, count * 4)):
                self.result_context = None
                self.previous_results.clear()
                return True
            results = {}
            for index in range(count):
                obj = memory.integer(array + index*4)
                if valid_pointer(obj, 0xC2) and memory.integer(obj + 0x1C) == RESULT_VTABLE:
                    results[obj] = memory.read(obj + 0xC0, 2)
            for flags in results.values():
                if flags[1] == 1 and ('win', self.active_minigame) in self.lookup:
                    checks.add(self.lookup['win', self.active_minigame])
                if flags[0] == 1 and ('perfect', self.active_minigame) in self.lookup:
                    checks.add(self.lookup['perfect', self.active_minigame])
            self.previous_results = {obj for obj, flags in results.items() if flags[1] == 1}
            self.result_context = context
            if minigame is not None or results or manager_state not in (5, 6):
                return True
            self.active_minigame = None
            self.result_context = None
            self.previous_results.clear()
        self.result_context = None
        self.previous_results.clear()
        hole_state = memory.integer(snapshot.root + 0x19C)
        pointers_valid = (valid_pointer(hole_state, 0x128) and valid_pointer(hole_def, 0x10)
                          and valid_pointer(controller, 0x20))
        goal = memory.integer(hole_state + 0x127, 1) if pointers_valid else None
        hole = derived_hole
        current_valid = pointers_valid and hole is not None
        context = (snapshot.root, hole_state, hole, controller) if current_valid else None
        completed_hole = hole if (current_valid and self.previous_hole == context) else None
        if completed_hole is None and pointers_valid and self.previous_hole is not None:
            old_root, old_state, old_hole, old_controller = self.previous_hole
            if ((old_root, old_state, old_controller) == (snapshot.root, hole_state, controller)
                    and 0 <= old_hole < 27):
                completed_hole = old_hole
        if completed_hole is not None and self.previous_goal == 0 and goal == 1:
            self.add_hole_completion(memory, snapshot.root, hole_def, completed_hole, checks)
        if not current_valid:
            self.previous_hole = self.previous_goal = None
            return False
        self.previous_hole, self.previous_goal = context, goal
        return True

    def debug_state(self, memory, local_player=0):
        snapshot = memory.resolve(local_player)
        def safe(read):
            try:
                return read()
            except (MemoryUnavailable, RuntimeError, OSError):
                return "ERR"

        result = {"manager": snapshot.manager, "root": snapshot.root, "session": snapshot.session,
                  "manager_state": safe(lambda: memory.integer(snapshot.manager + 0xBC)),
                  "session_player": "none", "course": "none", "controller": "none", "vtable": "none",
                  "hole_def": safe(lambda: memory.integer(snapshot.manager + 0x10C)),
                  "derived_hole": None, "strokes": safe(lambda: memory.integer(snapshot.root + 0x2DC)),
                  "par": "ERR", "hole_state": safe(lambda: memory.integer(snapshot.root + 0x19C)),
                  "in_goal": "ERR", "object_array": safe(lambda: memory.integer(snapshot.manager + 0x100)),
                  "result_popup": None, "win": None, "perfect": None,
                  "minigame": self.active_minigame}
        if snapshot.session is not None:
            result["session_player"] = safe(lambda: memory.integer(snapshot.session + 0x2EC))
            result["course"] = safe(lambda: memory.integer(snapshot.session + 0x2F0))
            result["controller"] = safe(lambda: memory.integer(snapshot.session + 0xFC))
        if isinstance(result["controller"], int) and valid_pointer(result["controller"], 0x20):
            result["vtable"] = safe(lambda: memory.integer(result["controller"] + 0x1C))
            if isinstance(result["vtable"], int):
                result["minigame"] = VTABLE_TO_WORLD.get(result["vtable"], self.active_minigame)
        if isinstance(result["hole_def"], int):
            result["derived_hole"] = self.derive_hole_id(memory, result["hole_def"])
            result["par"] = safe(lambda: memory.integer(result["hole_def"] + 0x0C))
        if isinstance(result["hole_state"], int) and valid_pointer(result["hole_state"], 0x128):
            result["in_goal"] = safe(lambda: memory.integer(result["hole_state"] + 0x127, 1))
        count = safe(lambda: memory.integer(snapshot.manager + 0x104))
        if (isinstance(result["object_array"], int) and isinstance(count, int) and 0 <= count <= 4096
                and valid_pointer(result["object_array"], max(4, count * 4))):
            for index in range(count):
                obj = safe(lambda i=index: memory.integer(result["object_array"] + i * 4))
                if isinstance(obj, int) and valid_pointer(obj, 0xC2):
                    obj_vtable = safe(lambda o=obj: memory.integer(o + 0x1C))
                    if obj_vtable == RESULT_VTABLE:
                        flags = safe(lambda o=obj: memory.read(o + 0xC0, 2))
                        result["result_popup"] = obj
                        if isinstance(flags, bytes):
                            result["perfect"], result["win"] = flags
                        break
        return result

    def victory(self, items, checks):
        _, coins = self.unlocked(items)
        goal = self.slot['goal']
        if goal == 2:
            return coins >= self.slot['required_coins']
        final = self.slot['goal_world']
        if goal == 1:
            if GOAL_WORLD_ACCESS not in {ID_TO_NAME.get(item) for item in items}:
                return False
            holes = range(final*3, final*3+3)
        else:
            return all(self.lookup['complete', i] in checks for i in range(27))
        return all(self.lookup['par', i] in checks for i in holes)
