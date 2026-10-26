from .wisps import wisp_level, all_wisps_owned
from .Items import ALL_WISP_ITEMS, RANDOM_CAPSULES, EMERALDS
from .world_constants import BY_MISSION, STAGES

STORY_PREVIOUS = {stage['mission_id']: tuple(
    earlier['mission_id'] for earlier in STAGES
    if earlier['zone_index']==stage['zone_index'] and 1<=earlier['slot']<stage['slot']
    and earlier['slot']<=6) for stage in STAGES if stage['zone_index']<6}

COLOURS = {
    'laser': 'Cyan Laser', 'drill': 'Yellow Drill', 'rocket': 'Orange Rocket',
    'cube': 'Blue Cube', 'hover': 'Green Hover', 'spikes': 'Pink Spikes',
    'frenzy': 'Purple Frenzy',
}
MOVEMENTS = {
    'wall_jump': 'Wall Jump', 'homing_attack': 'Homing Attack',
    'mid_air_boost': 'Mid-Air Boost', 'double_jump': 'Double Jump',
    'stomp': 'Stomp', 'crouch': 'Progressive Crouch',
    'breathing': 'Progressive Breathing', 'stunts': 'Progressive Stunts',
    'rail': 'Progressive Rail', 'skydiving': 'Progressive Skydiving',
    'swim': 'Swim', 'drifting': 'Drifting', 'quick_step': 'Quick Step',
    'assist_change': 'Assist Change',
}
SPECIAL = {'boost', 'all_wisps', 'land_speed', 'random_capsules'}
KNOWN = set(COLOURS) | set(MOVEMENTS) | SPECIAL


def selected(world, option):
    result = getattr(world.options, option)
    return bool(getattr(result, 'value', result))


def token_parts(token):
    if not isinstance(token, str) or not token:
        raise ValueError('Invalid logic token: ' + repr(token))
    parts = token.split(':')
    if len(parts) > 2 or parts[0] not in KNOWN or (len(parts) == 2 and
            (not parts[1].isdigit() or int(parts[1]) < 1)):
        raise ValueError('Unknown logic token: ' + token)
    return parts[0], int(parts[1]) if len(parts) == 2 else 1


def available(world, state, token):
    name, tier = token_parts(token)
    player = world.player
    if name == 'all_wisps':
        counts = {item: state.count(item, player) for item in ALL_WISP_ITEMS}
        return all_wisps_owned(counts, world.options)
    if name == 'boost':
        return not selected(world, 'boost_lock') or state.has('White Boost Wisp', player)
    if name in COLOURS:
        counts = {item: state.count(item, player) for item in ALL_WISP_ITEMS}
        return wisp_level(counts, COLOURS[name], world.options) >= tier
    if name == 'land_speed':
        # Lv1 is built into the game: first Progressive Speed item unlocks Lv2.
        return (not selected(world, 'game_land_checks') or
                not selected(world, 'movement_unlocks') or
                state.has('Progressive Game Land Speed', player, tier))
    if name == 'random_capsules':
        return state.has(RANDOM_CAPSULES, player)
    if name in MOVEMENTS:
        return not selected(world, 'movement_unlocks') or state.has(MOVEMENTS[name], player, tier)
    raise AssertionError('Unchecked token: ' + name)


def matches(world, state, routes):
    return any(all(available(world, state, token) for token in route) for route in routes)


def clear_route(world,state,manifest,mission):
    stage=BY_MISSION[mission]
    if (stage['kind']=='Act' and stage['zone_index']<7
            and bool(getattr(world.options,'super_sonic',False)) and not selected(world,'movement_unlocks')
            and all(state.has(item,world.player) for item in EMERALDS)):
        return True
    route_type='movement' if selected(world,'movement_unlocks') else 'normal'
    return matches(world,state,manifest['locations'][mission][route_type])


def check(world, state, manifest, key, rank=None):
    # Later Acts also need the earlier clear routes.
    stage=BY_MISSION.get(key.split(':',1)[0])
    progression=getattr(world.options,'world_progression',None)
    if stage and stage['zone_index']<6 and progression is not None:
        mode=getattr(progression,'value',progression)
        previous=STORY_PREVIOUS[stage['mission_id']] if mode==0 or stage['slot']==7 else ()
        if not all(clear_route(world,state,manifest,mission) for mission in previous):
            return False
    record = manifest['locations'][key]
    route_type = 'movement' if selected(world, 'movement_unlocks') else 'normal'
    if not matches(world, state, record[route_type]):
        return False
    if rank in ('S', 'A'):
        mission = key.split(':', 1)[0]
        if not all(available(world, state, wisp) for wisp in manifest['rank_wisps'].get(mission, [])):
            return False
        if rank == 'S' and selected(world, 'movement_unlocks'):
            extra = manifest['rank_s_extra_movement'].get(mission)
            if extra is not None and not matches(world, state, extra):
                return False
    elif rank is not None and rank not in ('B', 'C'):
        raise ValueError('Unknown rank: ' + str(rank))
    return True


def key_for_location(data):
    if data.kind in ('clear', 'rank'):
        return data.mission
    if data.kind == 'ring':
        return f'{data.mission}:ring:{data.index}'
    if data.kind == 'one_up':
        return f'{data.mission}:one_up'
    if data.kind == 'medal':
        return f'{data.mission}:eggman_heart'
    raise ValueError('No completed sheet logic for location type: ' + data.kind)


def validate_manifest(manifest):
    from .Locations import LOCATION_TABLE
    from .world_constants import STAGES
    if manifest.get('schema') != 'sonic_colours_poptracker_sheet_logic_v3':
        raise ValueError('Expected completed Sonic Colours V3 spreadsheet manifest')
    expected = {key_for_location(data) for data in LOCATION_TABLE.values()
                if data.kind in ('clear', 'ring', 'one_up', 'medal')}
    actual = set(manifest['locations'])
    if expected != actual or len(actual) != 298:
        raise ValueError('V3 route coverage mismatch: missing ' + repr(sorted(expected - actual))
                         + ', unexpected ' + repr(sorted(actual - expected)))
    missions = {s['mission_id'] for s in STAGES}
    for key, record in manifest['locations'].items():
        if key.split(':', 1)[0] not in missions:
            raise ValueError('Unknown stage in route: ' + key)
        for field in ('normal', 'movement', 'advanced_normal', 'advanced_movement'):
            routes = record[field]
            if not isinstance(routes, list):
                raise ValueError('Malformed route field: ' + key + ' ' + field)
            if field in ('normal', 'movement') and not routes:
                raise ValueError('Missing documented main route: ' + key + ' ' + field)
            for route in routes:
                if not isinstance(route, list):
                    raise ValueError('Malformed alternative route: ' + key)
                for token in route:
                    token_parts(token)
    for mission, tokens in manifest['rank_wisps'].items():
        if mission not in missions:
            raise ValueError('Unknown rank stage: ' + mission)
        for token in tokens:
            if token_parts(token)[0] not in (set(COLOURS) | {'boost', 'all_wisps'}):
                raise ValueError('Non-Wisp rank requirement: ' + str(token))
    for mission, alternatives in manifest['rank_s_extra_movement'].items():
        if mission not in missions or not alternatives:
            raise ValueError('Invalid S rank additional route: ' + mission)
        for route in alternatives:
            for token in route:
                token_parts(token)
    if manifest.get('unresolved_routes'):
        raise ValueError('Spreadsheet contains unresolved routes')
    return manifest
