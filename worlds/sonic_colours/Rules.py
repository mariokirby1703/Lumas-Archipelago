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
    if key == world.starting_stage['mission_id'] and world.starting_world == 6:
        return True
    entry = world.logic[key]
    if entry['logic_status'] == 'unknown':
        return state.has_all(WISP_ITEMS, world.player)
    return (state.has_all(entry['requires_all'], world.player)
            and (not entry['requires_any'] or state.has_any(entry['requires_any'], world.player)))


def set_rules(world):
    player = world.player
    for i, name in enumerate(WORLDS):
        entrance = world.get_region(name).entrances[0]
        if i != world.starting_world:
            set_rule(entrance, lambda state, item=WORLD_ITEMS[i]: state.has(item, player))
    for stage in STAGES:
        region = world.get_region('Map Slot ' + stage['stage_slot_id'])
        if stage['zone_index'] == 6 and stage['mission_id'] != world.starting_stage['mission_id']:
            set_rule(region.entrances[0], lambda state: (world.starting_world == 6 or state.has(WORLD_ITEMS[6], player))
                     and state.has_all(WISP_ITEMS, player))
        if stage['zone_index'] < 7:
            event_name = 'Story Clear Event ' + stage['mission_id']
            clear_event = SonicColoursLocation(player, event_name, None, region)
            clear_event.place_locked_item(Item(event_name, ItemClassification.progression, None, player))
            set_rule(clear_event, lambda state, mission=stage['mission_id']: requirements(world, state, mission))
            region.locations.append(clear_event)
        if stage['zone_index'] >= 7:
            gate = world.gates[f'{stage["zone_index"] - 6}-{stage["slot"]}']
            set_rule(region.entrances[0], lambda state, count=gate: sum(
                state.count(n, player) * amount for n, amount in RING_VALUES.items()) >= count)
            event_name = 'Game Land Clear Event ' + stage['mission_id']
            event = SonicColoursLocation(player, event_name, None, region)
            event.place_locked_item(Item(event_name, ItemClassification.progression, None, player))
            set_rule(event, lambda state, mission=stage['mission_id']: requirements(world, state, mission))
            region.locations.append(event)
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
            elif data.kind == 'emerald':
                missions = tuple(s['mission_id'] for s in STAGES if s['zone_index'] == stage['zone_index'])
                set_rule(location, lambda state, missions=missions: state.has_all(
                    ('Game Land Clear Event ' + m for m in missions), player))
            else:
                set_rule(location, lambda state, keys=keys: all(requirements(world, state, k) for k in keys))
    goal = world.options.goal.value
    if goal == 0:
        names = ['Story Clear Event stg790', 'Story Clear Event stg720']
    elif goal == 1:
        names = ['Story Clear Event ' + s['mission_id'] for s in STAGES if s['kind'] == 'Boss']
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
        set_rule(event, lambda state: state.has_all(('Game Land Clear Event ' + s['mission_id']
                for s in STAGES if s['zone_index'] >= 7), player))
    elif goal == 4:
        set_rule(event, lambda state: state.has_all(EMERALDS, player))
    else:
        set_rule(event, lambda state: state.has_all(names, player))
    world.multiworld.completion_condition[player] = lambda state: state.has('Sonic Colours Victory', player)
