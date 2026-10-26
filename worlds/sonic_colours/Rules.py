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


def requirements(world,state,key,rank=None):
    from .logic import check
    stage = BY_MISSION.get(key)
    if (rank is None and stage is not None and stage['kind'] == 'Act'
            and stage['zone_index'] < 7 and world.options.super_sonic
            and not world.options.movement_unlocks
            and all(state.has(emerald, world.player) for emerald in EMERALDS)):
        return True
    return check(world,state,world.logic,key,rank)


def all_wisps(world,state):
    from .wisps import all_wisps_owned
    from .Items import ALL_WISP_ITEMS
    return all_wisps_owned({n:state.count(n,world.player) for n in ALL_WISP_ITEMS},world.options)


def can_complete(world, state, mission):
    stage = BY_MISSION[mission]
    return (state.can_reach('Map Slot ' + stage['stage_slot_id'], 'Region', world.player)
            and requirements(world, state, mission))


def set_rules(world):
    player = world.player
    for i, name in enumerate(WORLDS):
        entrance = world.get_region(name).entrances[0]
        if i == 6:
            set_rule(entrance, lambda state: all_wisps(world,state))
        elif i != world.starting_world:
            set_rule(entrance, lambda state, item=WORLD_ITEMS[i]: state.has(item, player))
    for stage in STAGES:
        region = world.get_region('Map Slot ' + stage['stage_slot_id'])
        dependencies=()
        if stage['zone_index'] < 6 and stage['slot'] > 1:
            zone, slot = stage['zone_index'], stage['slot']
            previous = next(s['mission_id'] for s in STAGES if s['zone_index'] == zone and s['slot'] == slot - 1)
            all_acts = tuple(s['mission_id'] for s in STAGES if s['zone_index'] == zone and 1 <= s['slot'] <= 6)
            if slot == 7 and world.options.world_progression.value == 1:
                dependencies=all_acts
                set_rule(region.entrances[0], lambda state, missions=all_acts: all(
                    can_complete(world, state, m) for m in missions))
            elif world.options.world_progression.value == 0:
                dependencies=tuple(s['mission_id'] for s in STAGES
                                   if s['zone_index']==zone and 1<=s['slot']<slot)
                set_rule(region.entrances[0], lambda state, missions=dependencies: all(
                    can_complete(world,state,mission) for mission in missions))
        if stage['zone_index'] == 6:
            previous={'stg790':'stg710','stg720':'stg790'}.get(stage['mission_id'])
            dependencies=(previous,) if previous else ()
            set_rule(region.entrances[0], lambda state, previous=previous: all_wisps(world,state)
                     and (previous is None or can_complete(world,state,previous)))
        # Entrance rules inspect other regions through can_complete(). Tell
        # CollectionState to revisit them when those regions become reachable;
        # otherwise traversal order can strand a valid sequential route.
        for mission in dependencies:
            predecessor=world.get_region('Map Slot '+BY_MISSION[mission]['stage_slot_id'])
            world.multiworld.register_indirect_condition(predecessor,region.entrances[0])
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
                from .logic import available
                colour=item.removesuffix(' Wisp').removeprefix('Progressive ')
                set_rule(location,lambda state,colour=colour,story=CAPSULES[data.instance_key].story:
                         available(world,state, {'Cyan Laser':'laser','Yellow Drill':'drill',
                         'Orange Rocket':'rocket','Blue Cube':'cube',
                         'Green Hover':'hover','Pink Spikes':'spikes',
                         'Purple Frenzy':'frenzy','White Boost':'boost'}[colour]) and
                         (not world.options.game_land_checks or story or state.has('Random Capsules',player)))
            elif data.kind in ('one_up','medal'):
                from .logic import key_for_location
                set_rule(location,lambda state,key=key_for_location(data):requirements(world,state,key))
            elif data.kind=='rank':
                from .world_constants import RANKS
                set_rule(location,lambda state,mission=data.mission,rank=RANKS[data.index]:
                         can_complete(world,state,mission) and requirements(world,state,mission,rank))
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
    event = world.get_location('Sonic Colours Victory')
    if goal == 2:
        set_rule(event, lambda state: all(state.can_reach('Map Slot ' + s['stage_slot_id'], 'Region', player)
                and all(requirements(world, state, f'{s["mission_id"]}:ring:{i}') for i in range(1, 6))
                for s in STAGES if s['normal']))
    else:
        set_rule(event, lambda state: all(can_complete(world, state, mission) for mission in names))
    world.multiworld.completion_condition[player] = lambda state: state.has('Sonic Colours Victory', player)
