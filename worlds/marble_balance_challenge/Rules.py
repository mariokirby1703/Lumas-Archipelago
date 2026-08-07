from __future__ import annotations

from typing import TYPE_CHECKING

from rule_builder.rules import Has, HasAll, Rule

from . import Locations
from .Names import item_names as items, location_names, region_names
from .Options import Goal, HardModeUnlock
from .world_constants import BONUS_WORLDS, NORMAL_WORLDS

if TYPE_CHECKING:
    from .world import MarbleBalanceWorld


def can_access_hard_mode(world: MarbleBalanceWorld) -> Rule:
    if world.options.hard_mode_unlock == HardModeUnlock.option_start:
        return HasAll()
    if world.options.hard_mode_unlock == HardModeUnlock.option_item:
        return Has(items.HARD_MODE)
    if world.options.hard_mode_unlock == HardModeUnlock.option_green_gems:
        return Has(items.GREEN_GEM, count=world.options.required_green_gems_for_hard.value)
    return HasAll()


def goal_difficulty(world: MarbleBalanceWorld) -> str:
    return "Hard" if world.options.goal == Goal.option_hard_w7_l10 else "Normal"


def can_access_w7(world: MarbleBalanceWorld, difficulty: str) -> Rule:
    if world.options.stump_piece_sanity and difficulty == goal_difficulty(world):
        return Has(items.STUMP_TEMPLE_PIECE, count=world.options.required_stump_pieces_for_w7.value)
    return Has(items.world_access_name(difficulty, "W7"))


def world_access_rule(world: MarbleBalanceWorld, difficulty: str, normal_world: str) -> Rule:
    if normal_world == "W1":
        rule: Rule = HasAll()
    elif normal_world == "W5":
        rule = Has(items.world_access_name(difficulty, normal_world))
        if world.options.split_vehicle_world_access and difficulty != "Hard":
            rule = rule & Has(items.SUBMARINE)
    elif normal_world == "W6":
        rule = Has(items.world_access_name(difficulty, normal_world))
        if world.options.split_vehicle_world_access and difficulty != "Hard":
            rule = rule & Has(items.ROCKET_SHIP)
    elif normal_world == "W7":
        rule = can_access_w7(world, difficulty)
    else:
        rule = Has(items.world_access_name(difficulty, normal_world))

    if difficulty == "Hard":
        rule = rule & can_access_hard_mode(world)
    return rule


def set_entrance_rules(world: MarbleBalanceWorld) -> None:
    for difficulty in world.enabled_difficulties:
        for normal_world in NORMAL_WORLDS:
            entrance = world.get_entrance(f"Menu to {difficulty} {normal_world}")
            world.set_rule(entrance, world_access_rule(world, difficulty, normal_world))

    if world.options.split_vehicle_world_access:
        bonus_access = {
            "WA": Has(items.SUBMARINE) & Has(items.world_access_name("Normal", "W5")),
            "WB": Has(items.SUBMARINE) & Has(items.world_access_name("Normal", "W5")),
            "WC": Has(items.ROCKET_SHIP) & Has(items.world_access_name("Normal", "W6")),
        }
    else:
        bonus_access = {
            "WA": Has(items.world_access_name("Normal", "W5")),
            "WB": Has(items.world_access_name("Normal", "W5")),
            "WC": Has(items.world_access_name("Normal", "W6")),
        }
    for bonus_world in BONUS_WORLDS:
        world.set_rule(world.get_entrance(f"Menu to Normal {bonus_world}"), bonus_access[bonus_world])
        if "Hard" in world.enabled_difficulties:
            world.set_rule(world.get_entrance(f"Menu to Hard {bonus_world}"), can_access_hard_mode(world))


def set_completion_condition(world: MarbleBalanceWorld) -> None:
    difficulty = goal_difficulty(world)
    goal_location = world.get_location(location_names.goal_location_name(difficulty, "W7", 10))
    world.set_rule(goal_location, world_access_rule(world, difficulty, "W7"))
    world.set_completion_rule(Has(items.VICTORY))


def set_location_rules(world: MarbleBalanceWorld) -> None:
    for location in world.get_locations():
        data = Locations.LOCATION_TABLE.get(location.name)
        if data and data.world in BONUS_WORLDS and data.difficulty and data.level:
            world.set_rule(
                location,
                Has(items.bonus_level_unlock_name(data.difficulty, data.world, data.level)),
            )


def set_all_rules(world: MarbleBalanceWorld) -> None:
    set_entrance_rules(world)
    set_location_rules(world)
    set_completion_condition(world)
