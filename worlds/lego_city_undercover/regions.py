"""Source-backed AP regions with conservative, opt-in native area-pass logic.

The start is always Auburn (SF_Docks). Cherry Tree Hills, including the Police
Station, requires SF_Residential when area passes are enabled. Unknown resource
areas remain unresolved; no nearest-collectible inference is used. These AP
rules are not proof that the native game can always reject/undo every entrance.
"""
from BaseClasses import Region, ItemClassification
import json
import pkgutil
from pathlib import PurePosixPath

from .bridge.goals import ASSIGNMENTS
from .bridge.capabilities import has_capability
from .bridge.opening_logic import NO_POLICE_KEYS
from .bridge.source_logic import source_rule
from .bridge.research_profile import ABILITY_NAMES
from .bridge.area_passes import (
    canonical, has_area, START, FIRST, auburn_opening_key,
)
from .bridge.location_design import data

STORY_TOOLS = (
    ('Police', 'Scanner', 'Detective Scan', 'GrappleGun', 'SuperBuild'),
    ('Parkour',), ('Robber', 'Miner'), (), (), ('Astronaut',),
    ('Color Gun',), (), ('Farmer', 'Firefighter', 'FireAxe'),
    (), (), ('Construction Worker',), (), (), ('Jetpack',),
)
VICTORY = 'LCU Story Complete'


def district_name(value):
    aliases = {name.casefold(): name for name in ABILITY_NAMES
               if name.startswith(('SF_', 'WI_', 'NY_', 'IS_', 'BR_'))}
    aliases['ny_monaco_tunnel'] = 'NY_Tunnel'
    return aliases.get(str(value).casefold())


def create_regions(world, location_type, item_type):
    player = world.player
    multi = world.multiworld
    regions = {}

    def region(name):
        if name not in regions:
            regions[name] = Region(name, player, multi)
            multi.regions.append(regions[name])
        return regions[name]

    menu = region('Menu')
    opening = region('Opening before Police')
    city = region('LEGO City')
    menu.connect(opening)
    opening.connect(city)
    area_enabled = bool(world.options.area_pass_items.value)

    area_names = data('area_names.json')
    display_to_native = {display: native for native, display in area_names.items()}

    def row_district(row, key=None):
        """Never treat the Police Station as a district of Auburn.

        Older opening logic allowed station rewards before Police. That does
        not make their geographic area SF_Docks. The HQ is reached through
        Cherry Tree Hills in a district-gated seed.
        """
        source = str(row.get('source', '')).replace('\\', '/').lower()
        if key == 'story_disguise:COP' or '/police_station/' in source or source == 'police_station':
            return FIRST
        return (canonical(row.get('district')) or
                canonical(display_to_native.get(row.get('display_area'))))

    station = region('Police Station')
    city.connect(station, rule=lambda state:
                 not area_enabled or has_area(state, player, FIRST))

    for name in ABILITY_NAMES:
        if district_name(name) == name:
            city.connect(region('District: ' + name), rule=lambda state, name=name:
                         not area_enabled or has_area(state, player, name))

    requirements = []
    prior = city
    for index, assignment in enumerate(ASSIGNMENTS):
        target = region(f'Assignment {index + 1}: {assignment}')
        requirements.extend(STORY_TOOLS[index])
        needed = tuple(name for name in requirements
                       if name != 'Detective Scan' or world.options.detective_scan_lock.value)
        linear = world.options.story_mode.value == 0
        enabled = bool(world.options.ability_items.value)
        entry = world.active_catalogue.get('mission:' + assignment + ':Complete', {})
        entrance_area = row_district(entry)
        (prior if linear else city).connect(target,
            rule=lambda state, needed=needed, enabled=enabled, entrance_area=entrance_area:
                (not area_enabled or entrance_area is None or has_area(state, player, entrance_area))
                and (not enabled or all(has_capability(state, player, name) for name in needed)))
        prior = target

    scenes = json.loads(pkgutil.get_data(__package__, 'bridge/mission_scene_names.json'))
    sections = {}
    for scene, mission in scenes.items():
        if mission == 'blackwells_mansion':
            mission = ('blackwells_mansion_1' if scene.startswith('mansion1_')
                       else 'blackwells_mansion_2')
        parent = (station if mission == 'police_station' else
                  next((r for name, r in regions.items() if name.endswith(': ' + mission)), None))
        if parent is not None:
            section = region('Section: ' + scene)
            parent.connect(section)
            sections[scene] = section

    for key, row in world.active_catalogue.items():
        # The pre-Police catalogue spans BOTH Auburn and Cherry. With area
        # gating, only the genuinely reachable Auburn subset is in Opening.
        if key in NO_POLICE_KEYS and (not area_enabled or auburn_opening_key(key, row)):
            parent = opening
        elif key == 'story_disguise:COP' and area_enabled:
            parent = station
        elif key.startswith('mission:'):
            mission = key.split(':')[1]
            if mission == 'police_station':
                parent = station
            elif mission == 'blackwells_mansion':
                parent = region('Assignment 14: blackwells_mansion_2')
            else:
                parent = next((r for name, r in regions.items()
                               if name.endswith(': ' + mission)), city)
        else:
            source = str(row.get('source', '')).replace('\\', '/').lower()
            if '/police_station/' in source:
                parent = station
            elif '/standalones/' in source:
                mission = source.split('/standalones/')[1].split('/')[0]
                scene = PurePosixPath(source).stem.removesuffix('_tech')
                parent = sections.get(scene, next((r for name, r in regions.items()
                                    if name.endswith(': ' + mission)), city))
            elif district := row_district(row, key):
                name = 'District: ' + district
                if name not in regions:
                    city.connect(region(name), rule=lambda state, district=district:
                                 not area_enabled or has_area(state, player, district))
                parent = region(name)
            else:
                parent = region('City: unresolved source')

        if parent.name == 'City: unresolved source' and not parent.entrances:
            city.connect(parent)
        location = location_type(player, row['name'], row['id'], parent)
        location.access_rule = source_rule(
            row, player, bool(world.options.ability_items.value) and key not in NO_POLICE_KEYS,
            key=key,detective_randomized=bool(world.options.detective_scan_lock.value))
        if area_enabled and row_district(row, key) is None and parent.name == 'City: unresolved source':
            # Unresolved geography must not hide progression in an unreachable
            # area. Leave these candidates as non-progression while researching.
            location.item_rule = lambda item: not item.advancement
        parent.locations.append(location)

    if world.options.goal.value == 2:
        from . import TOKEN
        multi.completion_condition[player] = (
            lambda state: state.has(TOKEN, player, world.options.goal_tokens.value))
    else:
        goal = location_type(player, 'Story goal: final assignment', None, prior)
        prior.locations.append(goal)
        goal.place_locked_item(item_type(VICTORY, ItemClassification.progression, None, player))
        multi.completion_condition[player] = lambda state: state.has(VICTORY, player)
