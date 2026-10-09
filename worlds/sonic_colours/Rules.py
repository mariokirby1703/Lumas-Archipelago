from worlds.generic.Rules import set_rule
from BaseClasses import Item, ItemClassification
from .Locations import SonicColoursLocation
from .Items import WISP_ITEMS, WORLD_ITEMS, RING_VALUES
from .Locations import LOCATION_TABLE
from .world_constants import STAGES, WORLDS, BY_MISSION


def validate_logic(logic):
    for key, entry in logic.items():
        if entry.get('logic_status') not in ('known', 'unknown'):
            raise ValueError(f'{key}: logic_status must be known or unknown')
        if entry.get('fallback') != 'all_wisps' and entry['logic_status'] == 'unknown':
            raise ValueError(f'{key}: unknown logic requires explicit all_wisps fallback')
        for field in ('requires_all', 'requires_any'):
            if not isinstance(entry.get(field), list) or any(n not in WISP_ITEMS for n in entry[field]):
                raise ValueError(f'{key}: {field} must list valid Wisp item names')
    expected = {s['mission_id'] for s in STAGES}
    expected |= {f'{s["mission_id"]}:ring:{i}' for s in STAGES if s['normal'] for i in range(1, 6)}
    if expected - logic.keys():
        raise ValueError('Missing logic entries: ' + ', '.join(sorted(expected - logic.keys())))


def requirements(world, state, key):
    if not world.options.wisp_unlocks.value:
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
        if world.options.world_unlocks.value and i != world.starting_world:
            set_rule(entrance, lambda state, item=WORLD_ITEMS[i]: state.has(item, player))
        elif not world.options.world_unlocks.value and i > 0:
            previous = [s for s in STAGES if s['zone_index'] == i - 1 and s['kind'] == 'Boss'][0]
            set_rule(entrance, lambda state, n=previous['mission_id']: state.has('Clear Event ' + n, player))
    for stage in STAGES:
        region = world.get_region('Map Slot ' + stage['stage_slot_id'])
        if stage['kind'] == 'Boss' and not world.options.world_unlocks.value:
            event_name = 'Clear Event ' + stage['mission_id']
            event = SonicColoursLocation(player, event_name, None, region)
            event.place_locked_item(Item(event_name, ItemClassification.progression, None, player))
            set_rule(event, lambda state, mission=stage['mission_id']: requirements(world, state, mission))
            region.locations.append(event)
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
            set_rule(location, lambda state, keys=keys: all(requirements(world, state, k) for k in keys))
    goal = world.options.goal.value
    if goal == 0:
        names = [BY_MISSION['stg790']['name'] + ' - Clear']
    elif goal == 1:
        names = [s['name'] + ' - Clear' for s in STAGES if s['zone_index'] < 7]
    elif goal == 2:
        names = [n for n in world.active_locations if LOCATION_TABLE[n].kind in ('ring', 'rings')]
    else:
        names = [s['name'] + ' - Clear' for s in STAGES if s['zone_index'] >= 7]
    event = SonicColoursLocation(player, 'Sonic Colours Victory', None, world.get_region('Menu'))
    event.place_locked_item(Item('Sonic Colours Victory', ItemClassification.progression, None, player))
    world.get_region('Menu').locations.append(event)
    set_rule(event, lambda state: all(state.can_reach(n, 'Location', player) for n in names))
    world.multiworld.completion_condition[player] = lambda state: state.has('Sonic Colours Victory', player)
