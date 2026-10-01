"""Polling and item effects, testable with an in-memory Dolphin substitute."""
import struct
from ..Items import (BARKER_COIN, COIN_BUNDLE_DATA, COIN_TRAP_DATA,
                     ITEM_TABLE, PAR_CLUB_PIECES, UNLOCKS)
from ..Locations import LOCATION_TABLE
from ..data import HOLES, MINIGAMES, WORLDS
from .constants import (RESULT_VTABLE, ROOT_LOCKS, ROOT_SUB, SHOP_MANAGER_STATE,
                        MANAGER_STATE_MENU, MANAGER_STATE_MINIGAME, MINIGAME_MENU_POLLS)
from .memory import MemoryUnavailable, valid_pointer

ID_TO_NAME = {code: name for name, code in ITEM_TABLE.items()}
VTABLE_TO_MINIGAME = {data['vtable']: i for i, data in enumerate(MINIGAMES)}
WORLD_COUNT = len(WORLDS)
HOLE_COUNT = len(HOLES)


def validate_slot(data):
    if data.get('schema_version') != 9:
        raise ValueError("Unsupported Carnival Games MiniGolf slot-data version")
    start, final = data.get('starting_world'), data.get('goal_world')
    if type(start) is not int or not 0 <= start < WORLD_COUNT:
        raise ValueError("Invalid starting world")
    if final is not None and (type(final) is not int or not 0 <= final < WORLD_COUNT or final == start):
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
    if type(required) is not int or not (1 <= required <= 41 if data['counter_mode'] else required == 0):
        raise ValueError("Invalid Barker requirement")
    total = data.get('total_barker_coins')
    if type(total) is not int or not required <= total <= (required * 3 + 1) // 2:
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
        self.active_minigame = None
        self.pieces_projected = False
        self.shop_pieces_injected = False
        self.stable_non_minigame_polls = 0

    def reset_currency_context(self):
        self.journal.reset_confirmation()

    def reset_transient(self):
        self.reset_currency_context()
        self.active_minigame = None
        self.stable_non_minigame_polls = 0

    def unlocked(self, items):
        names = [ID_TO_NAME.get(item) for item in items]
        coins = names.count(BARKER_COIN)
        unlocked = {self.slot['starting_world']}
        unlocked.update(i for i, name in enumerate(UNLOCKS) if name in names)
        return unlocked, coins

    def poll(self, memory, items, local_player=0, history_ready=True, checked_locations=()):
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
        projected_on_previous_poll = self.pieces_projected
        if manager_state != SHOP_MANAGER_STATE and not projected_on_previous_poll:
            for hole, value in enumerate(persistent[0x86:0xA1]):
                if value == 1:
                    checks.add(self.lookup['par', hole])
        hole_def = memory.integer(snapshot.manager + 0x10C)
        derived_hole = self.derive_hole_id(memory, hole_def)
        try:
            self.read_transient(memory, snapshot, checks, derived_hole, hole_def, manager_state)
        except MemoryUnavailable:
            # A single failed MEM2 live-object read must not block persistent
            # roots, locations, locks, or receive-once item processing.
            pass
        if (history_ready and self.slot['goal_world_access'] == 1
                and coins >= self.slot['required_coins']):
            requirement = next((d.code for d in self.locations.values() if d.kind == 'barker_requirement'), None)
            if requirement is not None:
                checks.add(requirement)
        self.journal.add_checks(checks)
        memory.confirm(snapshot)
        locks = bytes(0 if i in unlocked else 1 for i in range(WORLD_COUNT))
        for player_root in (snapshot.root,):
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
                    self.apply_currency(memory, sub, index, 0x58 + 2*world, amount, 2)
                elif name in COIN_TRAP_DATA:
                    world, amount = COIN_TRAP_DATA[name]
                    self.apply_currency(memory, sub, index, 0x58 + 2*world, -amount, 2)
                elif name == BARKER_COIN and not self.slot['counter_mode']:
                    self.apply_currency(memory, sub, index, 0x85, 1, 1)
                else:
                    self.journal.advance(index)
                if self.journal.data["pending"] is not None:
                    break
        if (history_ready and self.slot['counter_mode']
                and snapshot.session is None
                and memory.integer(sub + 0x85, 1) != min(coins, 255)):
            memory.put(sub + 0x85, min(coins, 255))
            memory.put(sub + 0xA1, 1)
        received_names = [ID_TO_NAME[item] for item in items]
        shop_context = manager_state == SHOP_MANAGER_STATE
        if not shop_context:
            self.shop_pieces_injected = False
            known_checks = set(checked_locations) | set(self.journal.data['checks']) | checks
            # Menu/select screens display actual Par accomplishments. Gameplay
            # gets no AP inventory projection at all.
            pieces = (bytes(int(self.lookup['par', hole] in known_checks) for hole in range(HOLE_COUNT))
                      if manager_state == MANAGER_STATE_MENU else bytes(HOLE_COUNT))
            if memory.read(sub + 0x86, 27) != pieces:
                memory.write(sub + 0x86, pieces)
                if manager_state != MANAGER_STATE_MENU and not projected_on_previous_poll and any(persistent[0x86:0xA1]):
                    memory.put(sub + 0xA1, 1)
            self.pieces_projected = any(pieces)
        elif history_ready and not self.shop_pieces_injected:
            pieces = bytes(int(piece < min(3, received_names.count(name)))
                           for name in PAR_CLUB_PIECES for piece in range(3))
            memory.write(sub + 0x86, pieces)
            self.shop_pieces_injected = True
            self.pieces_projected = any(pieces)
        return set(self.journal.data['checks']) & {d.code for d in self.locations.values()}

    def apply_currency(self, memory, sub, index, offset, amount, size):
        address = sub + offset
        _, after = self.journal.grant(memory, sub, index, offset, amount, size)
        current = memory.integer(address, size)
        verified = current >= after if amount > 0 else current == after
        if not verified:
            raise MemoryUnavailable(f"Currency verification failed at 0x{address:08X}")

    def clear_piece_projection(self, memory, local_player=0):
        if not self.pieces_projected or not memory.verify_game():
            return
        snapshot = memory.resolve(local_player)
        memory.write(snapshot.root + ROOT_SUB + 0x86, bytes(HOLE_COUNT))
        self.pieces_projected = False
        self.shop_pieces_injected = False

    @classmethod
    def derive_hole_id(cls, memory, current):
        # One bounded MEM1 read replaces up to 108 cross-process reads. The
        # course field is deliberately not trusted without a verified table base.
        if not valid_pointer(current, 16) or current >= 0x81800000:
            return None
        start = current - min(HOLE_COUNT - 1, (current - 0x80004000) // 16) * 16
        try:
            records = list(struct.iter_unpack('>IIII', memory.read(start, current - start + 16)))
        except MemoryUnavailable:
            return None
        index = -1
        for record in reversed(records):
            if not all(valid_pointer(value) for value in record[:3]) or not 1 <= record[3] <= 20:
                break
            index += 1
        return index if index >= 0 else None

    def add_hole_completion(self, memory, root, hole_def, hole, checks):
        strokes = memory.integer(root + 0x2DC)
        par = memory.integer(hole_def + 0x0C)
        checks.add(self.lookup['complete', hole])
        if 1 <= strokes <= par <= 20:
            checks.add(self.lookup['par', hole])
        if strokes == 1 and ('hio', hole) in self.lookup:
            checks.add(self.lookup['hio', hole])

    def read_transient(self, memory, snapshot, checks, derived_hole, hole_def, manager_state):
        controller = None
        detected = None
        if snapshot.session is not None:
            try:
                controller = memory.integer(snapshot.session + 0xFC)
                if valid_pointer(controller, 0x20):
                    detected = VTABLE_TO_MINIGAME.get(memory.integer(controller + 0x1C))
            except MemoryUnavailable:
                pass  # Normal hole detection is independent of controller reads.

        # Main Adventure controllers can remain alive in holes B/C. They only
        # identify a current minigame on their world's Adventure hole.
        current_minigame = None
        if detected is not None and detected < 9:
            if derived_hole == MINIGAMES[detected]['world'] * 3:
                current_minigame = detected
        elif (detected is None and manager_state == MANAGER_STATE_MINIGAME
              and derived_hole is not None and derived_hole % 3 == 0):
            current_minigame = derived_hole // 3
        if current_minigame is not None:
            self.active_minigame = current_minigame
            self.stable_non_minigame_polls = 0

        # Spiders has no CMGResultsPopup. Live code requires all eleven object
        # states to reach 6; it intentionally has no Perfect location.
        if detected == 9 and controller is not None:
            if memory.read(controller + 0x1FC, 11) == bytes([6]) * 11:
                if ('win', 9) in self.lookup:
                    checks.add(self.lookup['win', 9])

        if self.active_minigame is not None:
            results = []
            try:
                array = memory.integer(snapshot.manager + 0x100)
                count = memory.integer(snapshot.manager + 0x104)
                if 0 < count <= 4096 and valid_pointer(array, count * 4):
                    pointers = struct.iter_unpack('>I', memory.read(array, count * 4))
                    for (obj,) in pointers:
                        try:
                            if valid_pointer(obj, 0xC2) and memory.integer(obj + 0x1C) == RESULT_VTABLE:
                                results.append(memory.read(obj + 0xC0, 2))
                        except MemoryUnavailable:
                            continue
            except MemoryUnavailable:
                pass
            for perfect, win in results:
                if win == 1 and ('win', self.active_minigame) in self.lookup:
                    checks.add(self.lookup['win', self.active_minigame])
                if perfect == 1 and ('perfect', self.active_minigame) in self.lookup:
                    checks.add(self.lookup['perfect', self.active_minigame])
            if current_minigame is None and manager_state in (MANAGER_STATE_MENU, SHOP_MANAGER_STATE):
                self.stable_non_minigame_polls += 1
                if self.stable_non_minigame_polls >= MINIGAME_MENU_POLLS:
                    self.active_minigame = None
            else:
                self.stable_non_minigame_polls = 0

        # A stale controller or latch never suppresses a real normal-hole
        # completion. State 7 is the sole guard against stale in_goal data while
        # actually entering an Adventure minigame.
        if snapshot.session is None or manager_state == MANAGER_STATE_MINIGAME:
            return
        hole_state = memory.integer(snapshot.root + 0x19C)
        if (derived_hole is not None and valid_pointer(hole_state, 0x128)
                and valid_pointer(hole_def, 0x10) and memory.integer(hole_state + 0x127, 1) == 1):
            self.add_hole_completion(memory, snapshot.root, hole_def, derived_hole, checks)

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
                  "spider_state": None, "spider_objects": None, "spider_complete": None,
                  "minigame": self.active_minigame}
        if snapshot.session is not None:
            result["session_player"] = safe(lambda: memory.integer(snapshot.session + 0x2EC))
            result["course"] = safe(lambda: memory.integer(snapshot.session + 0x2F0))
            result["controller"] = safe(lambda: memory.integer(snapshot.session + 0xFC))
        if isinstance(result["controller"], int) and valid_pointer(result["controller"], 0x20):
            result["vtable"] = safe(lambda: memory.integer(result["controller"] + 0x1C))
            if isinstance(result["vtable"], int):
                result["minigame"] = VTABLE_TO_MINIGAME.get(result["vtable"], self.active_minigame)
                if result["vtable"] == MINIGAMES[9]['vtable']:
                    result["spider_state"] = safe(lambda: memory.integer(result["controller"] + 0x212, 1))
                    result["spider_objects"] = safe(lambda: memory.read(result["controller"] + 0x1FC, 11))
                    result["spider_complete"] = result["spider_objects"] == bytes([6]) * 11
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
            if UNLOCKS[final] not in {ID_TO_NAME.get(item) for item in items}:
                return False
            holes = range(final*3, final*3+3)
        else:
            return all(self.lookup['complete', i] in checks for i in range(HOLE_COUNT))
        return all(self.lookup['par', i] in checks for i in holes)
