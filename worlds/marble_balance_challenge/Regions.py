from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Region

from .Names import region_names
from .world_constants import BONUS_WORLDS, NORMAL_WORLDS

if TYPE_CHECKING:
    from .world import MarbleBalanceWorld


def create_regions(world: MarbleBalanceWorld) -> None:
    regions = [
        Region(region_names.MENU, world.player, world.multiworld),
        Region(region_names.TUTORIALS, world.player, world.multiworld),
        Region(region_names.WII_BALANCE_BOARD, world.player, world.multiworld),
    ]

    for difficulty in world.enabled_difficulties:
        for normal_world in NORMAL_WORLDS:
            regions.append(Region(region_names.world_region_name(difficulty, normal_world), world.player, world.multiworld))

    for bonus_world in BONUS_WORLDS:
        regions.append(Region(region_names.world_region_name("Normal", bonus_world), world.player, world.multiworld))
        if "Hard" in world.enabled_difficulties:
            regions.append(Region(region_names.world_region_name("Hard", bonus_world), world.player, world.multiworld))

    world.multiworld.regions += regions


def connect_regions(world: MarbleBalanceWorld) -> None:
    menu = world.get_region(region_names.MENU)
    menu.connect(world.get_region(region_names.TUTORIALS), "Menu to Tutorials")
    menu.connect(world.get_region(region_names.WII_BALANCE_BOARD), "Menu to Wii Balance Board")

    for difficulty in world.enabled_difficulties:
        menu.connect(
            world.get_region(region_names.world_region_name(difficulty, "W1")),
            f"Menu to {difficulty} W1",
        )
        for normal_world in NORMAL_WORLDS[1:]:
            menu.connect(
                world.get_region(region_names.world_region_name(difficulty, normal_world)),
                f"Menu to {difficulty} {normal_world}",
            )

    for bonus_world in BONUS_WORLDS:
        menu.connect(
            world.get_region(region_names.world_region_name("Normal", bonus_world)),
            f"Menu to Normal {bonus_world}",
        )
        if "Hard" in world.enabled_difficulties:
            menu.connect(
                world.get_region(region_names.world_region_name("Hard", bonus_world)),
                f"Menu to Hard {bonus_world}",
            )


def create_and_connect_regions(world: MarbleBalanceWorld) -> None:
    create_regions(world)
    connect_regions(world)
