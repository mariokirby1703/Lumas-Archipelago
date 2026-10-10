from worlds.generic.Rules import set_rule
from BaseClasses import Item, ItemClassification
from .Locations import SonicColoursLocation
from .Items import WISP_ITEMS, WORLD_ITEMS, RING_VALUES, EMERALDS
from .Locations import LOCATION_TABLE
from .world_constants import STAGES, WORLDS, BY_MISSION
from .capsules import CAPSULES


def validate_logic(logic):
    for key, entry in logic.items():
        if entry.get('logic_status') not in ('known', 'unknown', 'provisional'):
            raise ValueError(f'{key}: invalid logic_status')
        if entry.get('fallback') != 'all_wisps' and entry['logic_status'] == 'unknown':
            raise ValueError(f'{key}: unknown logic requires explicit all_wisps fallback')
        if entry['logic_status'] == 'provisional' and (':ring:' in key or entry.get('fallback') != 'accessible_clear'):
            raise ValueError(f'{key}: provisional accessibility is only allowed for clear routes')
        for field in ('requires_all', 'requires_any'):
            if not isinstance(entry.get(field), list) or any(n not in WISP_ITEMS for n in entry[field]):
                raise ValueError(f'{key}: {field} must list valid Wisp item names')
    expected = {s['mission_id'] for s in STAGES}
    expected |= {f'{s["mission_id"]}:ring:{i}' for s in STAGES if s['normal'] for i in range(1, 6)}
    if expected - logic.keys():
        raise ValueError('Missing logic entries: ' + ', '.join(sorted(expected - logic.keys())))


def requirements(world, state, key):
    entry = world.logic[key]
    if entry['logic_status'] == 'unknown':
        return state.has_all(WISP_ITEMS, world.player)
    return (state.has_all(entry['requires_all'], world.player)
            and (not entry['requires_any'] or state.has_any(entry['requires_any'], world.player)))


def can_complete(world, state, mission):
    stage = BY_MISSION[mission]
    return (state.can_reach('Map Slot ' + stage['stage_slot_id'], 'Region', world.player)
            and requirements(world, state, mission))


def set_rules(world):
    player = world.player
    for i, name in enumerate(WORLDS):
        entrance = world.get_region(name).entrances[0]
        if i == 6:
            set_rule(entrance, lambda state: state.has_all(WISP_ITEMS, player))
        elif i != world.starting_world:
            set_rule(entrance, lambda state, item=WORLD_ITEMS[i]: state.has(item, player))
    for stage in STAGES:
        region = world.get_region('Map Slot ' + stage['stage_slot_id'])
        if stage['zone_index'] == 6:
            set_rule(region.entrances[0], lambda state: state.has_all(WISP_ITEMS, player))
        if stage['zone_index'] >= 7:
            gate = world.gates[f'{stage["zone_index"] - 6}-{stage["slot"]}']
            set_rule(region.entrances[0], lambda state, count=gate: sum(
                state.count(n, player) * amount for n, amount in RING_VALUES.items()) >= count)
        for location in region.locations:
            if location.address is None:
                continue
            data = LOCATION_TABLE[location.name]
            keys = ([f'{data.mission}:ring:{data.index}'] if data.kind == 'ring' else
                    [f'{data.mission}:ring:{i}' for i in range(1, 6)] if data.kind == 'rings' else [data.mission])
            if data.kind == 'capsule':
                item = CAPSULES[data.instance_key].wisp_item
                if item == 'White Boost Wisp' and not world.options.boost_lock:
                    set_rule(location, lambda state: True)
                else:
                    set_rule(location, lambda state, item=item: state.has(item, player))
            elif data.kind == 'medal':
                # The placement catalog proves identity, not an ability-free route.
                # Until individual routes are verified, require every Wisp in
                # addition to the physical Game Land stage's AP Ring gate.
                set_rule(location, lambda state: state.has_all(WISP_ITEMS, player))
            elif data.kind == 'emerald':
                missions = tuple(s['mission_id'] for s in STAGES if s['zone_index'] == stage['zone_index'])
                set_rule(location, lambda state, missions=missions: all(can_complete(world, state, m) for m in missions))
            else:
                set_rule(location, lambda state, keys=keys: all(requirements(world, state, k) for k in keys))
    goal = world.options.goal.value
    if goal == 0:
        names = ['stg790', 'stg720']
    elif goal == 1:
        names = [s['mission_id'] for s in STAGES if s['kind'] == 'Boss']
    elif goal == 2:
        names = []
    else:
        names = []
    event = SonicColoursLocation(player, 'Sonic Colours Victory', None, world.get_region('Menu'))
    event.place_locked_item(Item('Sonic Colours Victory', ItemClassification.progression, None, player))
    world.get_region('Menu').locations.append(event)
    if goal == 2:
        set_rule(event, lambda state: all(state.can_reach('Map Slot ' + s['stage_slot_id'], 'Region', player)
                and all(requirements(world, state, f'{s["mission_id"]}:ring:{i}') for i in range(1, 6))
                for s in STAGES if s['normal']))
    elif goal == 3:
        set_rule(event, lambda state: all(can_complete(world, state, s['mission_id'])
                for s in STAGES if s['zone_index'] >= 7))
    elif goal == 4:
        set_rule(event, lambda state: state.has_all(EMERALDS, player))
    else:
        set_rule(event, lambda state: all(can_complete(world, state, mission) for mission in names))
    world.multiworld.completion_condition[player] = lambda state: state.has('Sonic Colours Victory', player)
