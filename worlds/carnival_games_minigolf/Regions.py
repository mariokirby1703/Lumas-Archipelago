from BaseClasses import Region

from .Locations import LOCATION_TABLE, MiniGolfLocation
from .data import WORLDS


def create_regions(world):
    menu = Region("Menu", world.player, world.multiworld)
    world.multiworld.regions.append(menu)
    regions = {}
    for name in (*WORLDS, *(f"{name} Shop" for name in WORLDS), "Barker Shop"):
        region = Region(name, world.player, world.multiworld)
        world.multiworld.regions.append(region)
        menu.connect(region, f"Menu -> {name}")
        regions[name] = region
    for name in world.active_locations:
        data = LOCATION_TABLE[name]
        if data.kind in {"shop", "club"}:
            region = regions[f"{WORLDS[data.world]} Shop"]
        else:
            region = regions[WORLDS[data.world] if data.world is not None else "Barker Shop"]
        region.locations.append(MiniGolfLocation(world.player, name, data.code, region))
