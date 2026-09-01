from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Region

from . import game_data

if TYPE_CHECKING:
    from .world import CreateWorld


MENU = "Menu"
HUB = "Hub World"


def create_regions(world: CreateWorld) -> None:
    regions = [
        Region(MENU, world.player, world.multiworld),
        Region(HUB, world.player, world.multiworld),
    ]
    regions.extend(
        Region(game_data.region_name(world_key), world.player, world.multiworld)
        for world_key in world.active_world_keys
    )
    world.multiworld.regions += regions


def connect_regions(world: CreateWorld) -> None:
    menu = world.get_region(MENU)
    hub = world.get_region(HUB)
    menu.connect(hub, "Menu to Hub World")
    for world_key in world.active_world_keys:
        hub.connect(
            world.get_region(game_data.region_name(world_key)),
            f"Hub to {game_data.WORLD_NAMES[world_key]}",
        )


def create_and_connect_regions(world: CreateWorld) -> None:
    create_regions(world)
    connect_regions(world)
