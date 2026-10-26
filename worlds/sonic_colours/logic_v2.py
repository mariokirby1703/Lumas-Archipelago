from .wisps import required_wisp_items as pool_wisps,wisp_level
from .Items import ALL_WISP_ITEMS

COLOURS=('Cyan Laser','Yellow Drill','Orange Rocket','Blue Cube','Green Hover','Pink Spikes','Purple Frenzy')
PROGRESSIVE_COLOURS={'Yellow Drill','Green Hover','Pink Spikes'}
MOVEMENT_NAMES={'Wall Jump','Homing Attack','Mid-Air Boost','Double Jump','Stomp','Swim',
                'Drifting','Assist Change','Quick Step','Progressive Crouch',
                'Progressive Breathing','Progressive Stunts','Progressive Rail','Progressive Skydiving'}
SPECIAL_COLOUR_MOVES={'Yellow Drill Turbo':('Yellow Drill',2),
                      'Green Hover Ring Dash':('Green Hover',2),
                      'Pink Spikes Spin Dash':('Pink Spikes',2)}


def option(world,name):
    value=getattr(world.options,name)
    return bool(getattr(value,'value',value))


def wisp_item(colour, movement_unlocks):
    if colour=='White Boost':return 'White Boost Wisp'
    if colour not in COLOURS:raise ValueError('Unknown colour: '+str(colour))
    return ('Progressive ' if movement_unlocks and colour in PROGRESSIVE_COLOURS else '')+colour+' Wisp'


def required_wisp_items(world):
    return pool_wisps(world.options)


def colour_available(world,state,colour,tier=1):
    counts={name:state.count(name,world.player) for name in ALL_WISP_ITEMS}
    return wisp_level(counts,colour,world.options)>=tier


def available(world,state,atom):
    """Evaluate one abstract ability at a requested tier (progression-local)."""
    ability=atom.get('ability')
    if not ability:raise ValueError('Unknown/unparsed route token: '+str(atom))
    player=world.player
    movement=option(world,'movement_unlocks')
    if ability=='ALL_REQUIRED_WISPS':
        return all(colour_available(world,state,c) for c in ('White Boost',)+COLOURS)
    if ability=='White Boost':
        return not option(world,'boost_lock') or state.has('White Boost Wisp',player)
    if ability in COLOURS:
        return colour_available(world,state,ability,max(1,int(atom.get('tier',1))))
    if ability in SPECIAL_COLOUR_MOVES:
        colour,tier=SPECIAL_COLOUR_MOVES[ability]
        return colour_available(world,state,colour,tier if movement else 1)
    if ability=='Progressive Game Land Speed':
        return not (option(world,'game_land_checks') and movement) or state.has('Progressive Game Land Speed',player,max(1,int(atom.get('tier',1))))
    if ability in MOVEMENT_NAMES:
        if not movement:return True
        return state.has(ability,player,max(1,int(atom.get('tier',1))))
    raise ValueError('Unregistered abstract ability: '+str(ability))


def route_match(world,state,route):
    return all(available(world,state,atom) for atom in route)


def entry_match(world,state,entry,*,movement_field=False):
    """Never turn undocumented Normal routes into open routes.

    Missing movement notes are not proof of no ability requirement, but are
    intentionally left unconstrained pending user research.
    """
    if movement_field and not option(world,'movement_unlocks'):return True
    status=entry['status']
    if status=='not_documented':
        if movement_field:return True
        return all(state.has(item,world.player) for item in required_wisp_items(world))
    routes=entry['routes']
    if not routes or status=='needs_review':
        # Unresolved routes require review before release.
        raise ValueError('Ambiguous or unparsed route: '+entry.get('raw',''))
    # The sheet importer has already parsed conventional AND-before-OR
    # precedence into distinct routes. Keep the ambiguity review note for
    # human confirmation, but never silently replace alternatives with AND.
    # Advanced routes stay excluded because they live in a separate field.
    return any(route_match(world,state,route) for route in routes)


def check(world,state,manifest,key,rank=None):
    """Select NL or ML routes, never require both alternative strategies.

    A documented ML route may deliberately replace an NL Wisp route (e.g.
    alternative movement path). Absent ML notes inherit NL in the sheet
    manifest, rather than allowing the pickup for free.
    """
    record=manifest['locations'][key]
    movement=option(world,'movement_unlocks')
    branch=record['movement'] if movement else record['normal']
    if branch['status']=='not_documented':
        branch=record['normal']
    if not entry_match(world,state,branch):return False
    if rank:
        rank_entry=manifest['rank_observations'].get(record['mission_id'],{}).get('logic',{}).get(rank)
        if rank_entry:
            if rank_entry['status']=='needs_review':
                raise ValueError('Unreviewed rank strategy: '+key+' '+str(rank))
            if movement and 'movement_routes' in rank_entry:
                selected={**rank_entry,'routes':rank_entry['movement_routes']}
                return entry_match(world,state,selected)
            return entry_match(world,state,rank_entry)
    return True


def all_five_rings(world,state,manifest,mission):
    """All 5 Red Rings location = AND of the five *individual* ring routes."""
    return all(check(world,state,manifest,f'{mission}:ring:{i}') for i in range(1,6))


def key_for_location(data):
    """Convert existing LocationData kind/mission/index to V2 keys."""
    mission=data.mission
    if data.kind in ('clear','rank'):return mission
    if data.kind=='ring':return f'{mission}:ring:{data.index}'
    if data.kind=='one_up':return f'{mission}:one_up'
    if data.kind=='medal':return f'{mission}:eggman_heart'
    raise ValueError('No sheet logic for this location type: '+data.kind)


def validate_manifest(manifest):
    """Validate the exact catalog coverage and executable tokens before fill."""
    from .Locations import LOCATION_TABLE
    from .world_constants import STAGES
    if manifest.get('schema')!='sonic_colours_sheet_logic_v2_draft':raise ValueError('Unsupported Sheet Logic V2 schema')
    expected={key_for_location(data) for data in LOCATION_TABLE.values() if data.kind in ('clear','ring','one_up','medal')}
    actual=set(manifest['locations'])
    if actual!=expected or len(actual)!=298:
        raise ValueError('Sheet location mismatch: missing='+str(sorted(expected-actual))+' extra='+str(sorted(actual-expected)))
    abilities=set(COLOURS)|MOVEMENT_NAMES|set(SPECIAL_COLOUR_MOVES)|{'ALL_REQUIRED_WISPS','White Boost','Progressive Game Land Speed'}
    for key,record in manifest['locations'].items():
        if not key.startswith(record['mission_id']):raise ValueError('Sheet mission/key mismatch: '+key)
        for field in ('normal','movement'):
            entry=record[field]
            if entry['status']=='not_documented':
                if entry['routes'] is not None:raise ValueError('Undocumented routes must be null: '+key)
                continue
            if entry['status'] not in ('documented','special') or not entry['routes']:raise ValueError('Unparsed sheet route: '+key)
            for route in entry['routes']:
                for atom in route:
                    if atom.get('ability') not in abilities or type(atom.get('tier',1)) is not int or atom.get('tier',1)<1:
                        raise ValueError('Unknown sheet token: '+key+' '+str(atom))
    for mission,row in manifest['rank_observations'].items():
        if mission not in {s['mission_id'] for s in STAGES}:raise ValueError('Unknown rank mission: '+mission)
        for rank,entry in row['logic'].items():
            if rank not in ('S','A','B','C'):raise ValueError('Unknown rank label')
            if entry['status']=='needs_review':
                if mission!='stg650' or rank!='S':raise ValueError('Unrecognized unparsed rank route')
                continue
            for field in ('routes','movement_routes'):
                for route in entry.get(field) or []:
                    if any(a.get('ability') not in abilities or type(a.get('tier',1)) is not int
                           or a.get('tier',1)<1 for a in route):
                        raise ValueError('Unknown rank token: '+mission+' '+field)
    return manifest
