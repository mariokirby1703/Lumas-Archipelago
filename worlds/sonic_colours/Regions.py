from BaseClasses import Region
from .Locations import SonicColoursLocation, LOCATION_TABLE
from .world_constants import STAGES, WORLDS


def create_regions(world):
    menu = Region('Menu', world.player, world.multiworld)
    world.multiworld.regions.append(menu)
    for name in WORLDS + tuple(f'Game Land {i}' for i in range(1, 8)):
        region = Region(name, world.player, world.multiworld)
        world.multiworld.regions.append(region)
        menu.connect(region)
    for stage in STAGES:
        parent_name = stage['world'] if stage['zone_index'] < 7 else f'Game Land {stage["zone_index"] - 6}'
        parent = world.get_region(parent_name)
        region = Region('Map Slot ' + stage['stage_slot_id'], world.player, world.multiworld)
        world.multiworld.regions.append(region)
        parent.connect(region)
        for name in world.active_locations:
            data = LOCATION_TABLE[name]
            if data.mission == stage['mission_id']:
                region.locations.append(SonicColoursLocation(world.player, name, data.code, region))
