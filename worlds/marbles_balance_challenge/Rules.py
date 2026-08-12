from __future__ import annotations

from itertools import combinations
from typing import TYPE_CHECKING

from rule_builder.rules import CanReachLocation, Has, HasAll, Rule

from . import Locations
from .Names import item_names as items, location_names
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
        return Has(items.HARD_MODE)
    return HasAll()


def goal_difficulty(world: MarbleBalanceWorld) -> str:
    return "Hard" if world.options.goal == Goal.option_stump_temple_level_10_hard else "Normal"


def can_access_w7(world: MarbleBalanceWorld, difficulty: str) -> Rule:
    return Has(items.world_access_name(difficulty, "W7"))


def world_access_rule(world: MarbleBalanceWorld, difficulty: str, normal_world: str) -> Rule:
    is_starting_world = world.starting_worlds_by_difficulty.get(difficulty) == normal_world

    if is_starting_world and not (
        world.options.split_vehicle_world_access
        and difficulty != "Hard"
        and normal_world in {"W5", "W6"}
    ):
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


def bonus_world_access_rule(world: MarbleBalanceWorld, difficulty: str, bonus_world: str) -> Rule:
    if world.starting_worlds_by_difficulty.get(difficulty) == bonus_world:
        rule: Rule = HasAll()
    else:
        rule = Has(items.world_access_name(difficulty, bonus_world))
    if difficulty == "Hard":
        rule = rule & can_access_hard_mode(world)
    return rule


def bonus_world_late_levels_rule(difficulty: str, bonus_world: str) -> Rule:
    opening_goals = [
        CanReachLocation(location_names.goal_location_name(difficulty, bonus_world, level))
        for level in range(1, 6)
    ]
    rules: list[Rule] = []
    for combo in combinations(opening_goals, 3):
        rule = combo[0] & combo[1] & combo[2]
        rules.append(rule)

    combined = rules[0]
    for rule in rules[1:]:
        combined = combined | rule
    return combined


def set_entrance_rules(world: MarbleBalanceWorld) -> None:
    for difficulty in world.enabled_difficulties:
        for normal_world in NORMAL_WORLDS:
            entrance = world.get_entrance(f"Menu to {difficulty} {normal_world}")
            world.set_rule(entrance, world_access_rule(world, difficulty, normal_world))

    for bonus_world in BONUS_WORLDS:
        world.set_rule(
            world.get_entrance(f"Menu to Normal {bonus_world}"),
            bonus_world_access_rule(world, "Normal", bonus_world),
        )
        if "Hard" in world.enabled_difficulties:
            world.set_rule(
                world.get_entrance(f"Menu to Hard {bonus_world}"),
                bonus_world_access_rule(world, "Hard", bonus_world),
            )


def set_completion_condition(world: MarbleBalanceWorld) -> None:
    difficulty = goal_difficulty(world)
    goal_location = world.get_location(location_names.goal_location_name(difficulty, "W7", 10))
    world.set_rule(goal_location, world_access_rule(world, difficulty, "W7"))
    world.set_completion_rule(Has(items.VICTORY))


def set_counter_event_rules(world: MarbleBalanceWorld) -> None:
    difficulty = goal_difficulty(world)
    w7_name = Locations.counter_stump_unlock_name(
        difficulty,
        world.options.required_stump_pieces_for_w7.value,
    )
    world.set_rule(
        world.get_location(w7_name),
        Has(
            items.STUMP_TEMPLE_PIECE,
            count=world.options.required_stump_pieces_for_w7.value,
        ),
    )
    if world.options.hard_mode_unlock == HardModeUnlock.option_green_gems:
        hard_name = Locations.counter_hard_mode_name(
            world.options.required_green_gems_for_hard.value,
        )
        world.set_rule(
            world.get_location(hard_name),
            Has(
                items.GREEN_GEM,
                count=world.options.required_green_gems_for_hard.value,
            ),
        )


def set_location_rules(world: MarbleBalanceWorld) -> None:
    for location in world.get_locations():
        data = Locations.LOCATION_TABLE.get(location.name)
        if (
            data
            and data.difficulty
            and data.world
            and data.level
            and data.world not in BONUS_WORLDS
        ):
            world.set_rule(location, world_access_rule(world, data.difficulty, data.world))

        if data and data.world in BONUS_WORLDS and data.difficulty and data.level:
            rule = bonus_world_access_rule(world, data.difficulty, data.world)
            if data.level > 5:
                rule = rule & bonus_world_late_levels_rule(data.difficulty, data.world)
            world.set_rule(location, rule)


def set_all_rules(world: MarbleBalanceWorld) -> None:
    set_entrance_rules(world)
    set_location_rules(world)
    set_completion_condition(world)
    set_counter_event_rules(world)
