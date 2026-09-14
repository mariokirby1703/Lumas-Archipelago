"""Polling and item effects, testable with an in-memory Dolphin substitute."""
from ..Items import BARKER_COIN, COIN_BUNDLE_DATA, COIN_TRAP_DATA, ITEM_TABLE, UNLOCKS
from ..Locations import LOCATION_TABLE
from ..data import MINIGAMES
from .constants import RESULT_VTABLE, ROOT_LOCKS, ROOT_SUB
from .memory import MemoryUnavailable, valid_pointer

ID_TO_NAME = {code: name for name, code in ITEM_TABLE.items()}
VTABLE_TO_WORLD = {vtable: i for i, (_, vtable) in enumerate(MINIGAMES)}


def validate_slot(data):
    if data.get('schema_version') != 3:
        raise ValueError("Unsupported Carnival Games MiniGolf slot-data version")
    start, final = data.get('starting_world'), data.get('goal_world')
    if type(start) is not int or not 0 <= start < 9:
        raise ValueError("Invalid starting world")
    if final is not None and (type(final) is not int or not 0 <= final < 9 or final == start):
        raise ValueError("Invalid goal world")
    if type(data.get('counter_mode')) is not bool:
        raise ValueError("Invalid Barker mode")
    if final is not None and not data['counter_mode']:
        raise ValueError("Final-world gating requires Barker counter mode")
    required = data.get('required_coins')
    if type(required) is not int or not (1 <= required <= 27 if data['counter_mode'] else required == 0):
        raise ValueError("Invalid Barker requirement")
    if not isinstance(data.get('locations'), dict):
        raise ValueError("Missing MiniGolf location data")
    for name, value in data['locations'].items():
        if name not in LOCATION_TABLE or value.get('code') != LOCATION_TABLE[name].code:
            raise ValueError("Unknown MiniGolf location mapping")
        if data['counter_mode'] and LOCATION_TABLE[name].kind == 'barker_shop':
            raise ValueError("Barker Shop is incompatible with counter goals")
    if not all(name in data['locations'] for name, d in LOCATION_TABLE.items() if d.kind == 'par'):
        raise ValueError("Slot is missing mandatory par checks")


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

    def reset_transient(self):
        self.previous_hole = None
        self.previous_goal = None
        self.result_context = None
        self.previous_results.clear()

    def unlocked(self, items):
        names = [ID_TO_NAME.get(item) for item in items]
        coins = names.count(BARKER_COIN)
        unlocked = {self.slot['starting_world']}
        unlocked.update(i for i, name in enumerate(UNLOCKS) if name in names and i != self.slot['goal_world'])
        if self.slot['goal_world'] is not None and coins >= self.slot['required_coins']:
            unlocked.add(self.slot['goal_world'])
        return unlocked, coins

    def poll(self, memory, items, local_player=0):
        if not memory.verify_game():
            self.reset_transient()
            raise MemoryUnavailable("Waiting for supported Carnival Games MiniGolf (RG9P54, verified revision)")
        cursor = self.journal.data['cursor']
        if cursor > len(items):
            raise MemoryUnavailable("Waiting for complete AP received-item history")
        if any(item not in ID_TO_NAME for item in items):
            raise ValueError("Unknown received MiniGolf item ID; update the client")
        snapshot = memory.resolve(local_player)
        root, sub = snapshot.root, snapshot.root + ROOT_SUB
        # Capture persistent state before any AP writes.
        persistent = memory.read(sub, 0xA2)
        unlocked, coins = self.unlocked(items)
        checks = set()
        for data in self.locations.values():
            if data.world is not None and data.world not in unlocked:
                continue
            offset = {'par': 0x86, 'barker': 0x6A, 'shop': 0, 'club': 0, 'secret': 0, 'barker_shop': 0}.get(data.kind)
            if offset is not None and persistent[offset + data.index] == 1:
                checks.add(data.code)
        self.read_transient(memory, snapshot, unlocked, checks)
        memory.confirm(snapshot)
        self.journal.add_checks(checks)
        locks = bytes(0 if i in unlocked else 1 for i in range(9))
        for player_root in snapshot.roots:
            if memory.read(player_root + ROOT_LOCKS, 9) != locks:
                memory.write(player_root + ROOT_LOCKS, locks)
                memory.put(player_root + ROOT_SUB + 0xA1, 1)
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
        if self.slot['counter_mode'] and memory.integer(sub + 0x85, 1) != min(coins, 255):
            memory.put(sub + 0x85, min(coins, 255))
            memory.put(sub + 0xA1, 1)
        return set(self.journal.data['checks']) & {d.code for d in self.locations.values()}

    def read_transient(self, memory, snapshot, unlocked, checks):
        session = snapshot.session
        if session is None:
            self.reset_transient()
            return
        player = memory.integer(session + 0x2EC)
        controller = memory.integer(session + 0xFC)
        vtable = memory.integer(controller + 0x1C) if valid_pointer(controller, 0x134) else None
        minigame = VTABLE_TO_WORLD.get(vtable)
        if minigame is not None:
            self.previous_hole = self.previous_goal = None
            owner = memory.integer(controller + 0x44)
            context = (snapshot.root, controller, minigame)
            array = memory.integer(snapshot.manager + 0x100)
            count = memory.integer(snapshot.manager + 0x104)
            if count > 4096 or not valid_pointer(array, max(4, count * 4)):
                self.result_context = None
                self.previous_results.clear()
                return
            results = {}
            for index in range(count):
                obj = memory.integer(array + index*4)
                if valid_pointer(obj, 0xC2) and memory.integer(obj + 0x1C) == RESULT_VTABLE:
                    results[obj] = memory.read(obj + 0xC0, 2)
            # A popup already present when attaching/changing minigames is not a new result.
            if context == self.result_context and owner == snapshot.root and minigame in unlocked:
                for obj, flags in results.items():
                    if obj not in self.previous_results and flags[1] == 1:
                        if ('win', minigame) in self.lookup:
                            checks.add(self.lookup['win', minigame])
                        if flags[0] == 1 and ('perfect', minigame) in self.lookup:
                            checks.add(self.lookup['perfect', minigame])
            # Allow a newly allocated popup to finish populating its flags on a later poll.
            self.previous_results = {obj for obj, flags in results.items() if flags[1] == 1}
            if context != self.result_context:
                self.previous_results = set(results)
            self.result_context = context
            return
        self.result_context = None
        self.previous_results.clear()
        hole = memory.integer(session + 0x2F0)
        hole_state = memory.integer(snapshot.root + 0x19C)
        hole_def = memory.integer(snapshot.manager + 0x10C)
        if (player != snapshot.local_player or not 0 <= hole < 27 or hole // 3 not in unlocked
                or not valid_pointer(hole_state, 0x128) or not valid_pointer(hole_def, 0x10)
                or not valid_pointer(controller, 0x20)):
            self.previous_hole = self.previous_goal = None
            return
        goal = memory.integer(hole_state + 0x127, 1)
        context = (snapshot.root, hole_state, hole, controller)
        if self.previous_hole == context and self.previous_goal == 0 and goal == 1:
            strokes = memory.integer(snapshot.root + 0x2DC)
            par = memory.integer(hole_def + 0x0C)
            if 1 <= strokes <= par <= 20:
                checks.add(self.lookup['par', hole])
            if strokes == 1 and ('hio', hole) in self.lookup:
                checks.add(self.lookup['hio', hole])
        self.previous_hole, self.previous_goal = context, goal

    def victory(self, items, checks):
        _, coins = self.unlocked(items)
        if self.slot['counter_mode'] and coins < self.slot['required_coins']:
            return False
        final = self.slot['goal_world']
        if final is not None:
            holes = range(final*3, final*3+3)
        elif self.slot['counter_mode']:
            return True
        else:
            holes = range(27)
        return all(self.lookup['par', i] in checks for i in holes)
