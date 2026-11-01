"""Seed permissions installed before the first game frame."""
from collections import Counter
import struct

VERSION = 1


def validate_items(items):
    from ..Items import ITEM_TABLE
    known = set(ITEM_TABLE.values())
    if (not isinstance(items, list) or len(items) > 10000
            or any(type(item) is not int or item not in known for item in items)):
        raise ValueError('invalid starting item IDs')
    return items


def initialize(payload, hooks, options, initial_items=()):
    from ..Items import ITEM_TABLE, MOVEMENT_ITEMS
    from ..wisps import project_inventory, wisp_level
    from . import movement_gate, capsule_refresh, quick_step, skydiving, stunts
    from . import drill_turbo, hover_ring_dash, gameplay_controls, player_switch
    from .native_dol import ARENA
    from .test_inventory import MAXIMUM

    validate_items(list(initial_items))
    names = {code: name for name, code in ITEM_TABLE.items()}
    counts = Counter(names[item] for item in initial_items)
    owned = project_inventory({'counts': counts}, options)['counts']
    movement = bool(options.get('movement_unlocks', True))
    if not movement:
        owned = owned.copy()
        for name in MOVEMENT_ITEMS:
            owned[name] = MAXIMUM.get(name, 1)
    data = bytearray(payload)
    targets = {hook['hook']: hook['target'] for hook in hooks}
    applied = {}

    def write(hook, offset, *values):
        address = targets[hook] + offset
        packed = struct.pack('>' + 'I' * len(values), *values)
        start = address - ARENA
        if start < 0 or start + len(packed) > len(data):
            raise ValueError('boot permission outside native payload')
        if any(data[start:start + len(packed)]):
            raise ValueError('boot permission overwrites nonzero native data')
        data[start:start + len(packed)] = packed
        applied[f'{address:08x}'] = list(values)
        return address

    write(movement_gate.HOOK, movement_gate.payload(gecko=True)[2],
          movement_gate.MENU_POLICY_ARMED, movement_gate.permissions(owned))
    for module, value in (
        (quick_step, int(owned['Quick Step'] > 0)),
        (skydiving, int(owned['Progressive Skydiving'] == 0)),
        (stunts, min(5, owned['Progressive Stunts'])),
        (player_switch, int(owned['Assist Change'] > 0)),
        (drill_turbo, int(wisp_level(owned, 'Yellow Drill') >= 2)),
        (hover_ring_dash, int(wisp_level(owned, 'Green Hover') >= 2)),
    ):
        write(module.HOOK, module.payload()[1], value)

    white = int(not options.get('boost_lock', True) or owned['White Boost Wisp'] > 0)
    random = int(not options.get('game_land_checks', True) or owned['Random Capsules'] > 0)
    words = capsule_refresh.payload_words(compact_abi=True, epilogue_abi=True, cache_permissions=True)
    offset = capsule_refresh.data_offset(words)
    address = targets[capsule_refresh.HOOK] + offset
    # These hooks only compare a byte with the selected index. An immutable
    # zero byte in their own index word works before a save container exists.
    # The client replaces this pair with the attributed native profile later.
    write(capsule_refresh.HOOK, offset, address + 4, 0, white | random << 1)
    for kind in ('boost_use', 'boost_query', 'boost_add'):
        hook = gameplay_controls.HOOKS[kind][0]
        offset = gameplay_controls.payload(kind)[1]
        address = targets[hook] + offset
        write(hook, offset, address + 4, 0, 4, 0, 1-white)
    for kind in ('speed_get', 'speed_set', 'speed_ui'):
        hook = gameplay_controls.HOOKS[kind][0]
        offset = gameplay_controls.payload(kind)[1]
        address = targets[hook] + offset
        speed = min(4, owned['Progressive Game Land Speed']) if movement and options.get('game_land_checks', True) else 4
        write(hook, offset, address + 4, 0, speed)
    return bytes(data), applied
