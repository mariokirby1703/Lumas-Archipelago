from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from BaseClasses import Location

from .Addresses import addresses
from .Names import location_names as names
from .world_constants import (
    BONUS_WORLDS,
    DIFFICULTIES,
    LEVELS_PER_WORLD,
    LOCATION_ID_BASE,
    NORMAL_WORLDS,
    GAME_NAME,
)
from .Options import TrophySanity

if TYPE_CHECKING:
    from .world import MarbleBalanceWorld


def counter_stump_unlock_name(difficulty: str, required: int) -> str:
    piece = "Piece" if required == 1 else "Pieces"
    return f"Stump Temple {difficulty} Unlock ({required} Stump Temple {piece})"


def counter_hard_mode_name(required: int) -> str:
    gem = "Gem" if required == 1 else "Gems"
    return f"Hard Mode ({required} Green {gem})"


@dataclass(frozen=True)
class LocationData:
    code: int
    category: str
    difficulty: str | None = None
    world: str | None = None
    level: int | None = None
    address: dict[str, int | None] | None = None


class MarbleBalanceLocation(Location):
    game = GAME_NAME


def iter_campaign_stage_names() -> list[LocationData]:
    locations: list[LocationData] = []
    next_id = LOCATION_ID_BASE + 1

    def add(name: str, category: str, difficulty: str | None = None, world: str | None = None,
            level: int | None = None, address: dict[str, int | None] | None = None) -> None:
        nonlocal next_id
        locations.append(LocationData(next_id, category, difficulty, world, level, address))
        LOCATION_TABLE[name] = locations[-1]
        next_id += 1

    LOCATION_TABLE.clear()

    for required in range(1, 91):
        add(counter_stump_unlock_name("Normal", required), "counter_stump_unlock", difficulty="Normal", world="W7")
        add(counter_stump_unlock_name("Hard", required), "counter_stump_unlock", difficulty="Hard", world="W7")
    for required in range(0, 61):
        add(counter_hard_mode_name(required), "counter_hard_mode")

    for index in range(1, 11):
        add(names.tutorial_location_name(index), "tutorial", level=index)

    for difficulty in DIFFICULTIES:
        for world in NORMAL_WORLDS:
            for level in range(1, LEVELS_PER_WORLD[world] + 1):
                record = addresses.normal_level_record(difficulty, world, level)
                add(names.goal_location_name(difficulty, world, level), "goal", difficulty, world, level, record)
                for trophy in TROPHY_TIERS:
                    add(
                        names.trophy_location_name(difficulty, world, level, trophy),
                        f"{trophy.lower()}_trophy",
                        difficulty,
                        world,
                        level,
                        record,
                    )
                if difficulty != "Hard" and level <= 10:
                    add(names.green_gem_location_name(difficulty, world, level), "green_gem", difficulty, world, level, record)
                if record["stump_piece"] is not None and level <= 10:
                    add(names.stump_piece_location_name(difficulty, world, level), "stump_piece", difficulty, world, level, record)
                if difficulty == "Hard" and level <= 10:
                    add(names.ant_location_name(difficulty, world, level), "ant", difficulty, world, level, record)

    for world in BONUS_WORLDS:
        for level in range(1, LEVELS_PER_WORLD[world] + 1):
            record = addresses.bonus_level_record("Normal", world, level)
            add(names.goal_location_name("Normal", world, level), "bonus_goal", "Normal", world, level, record)
            for trophy in TROPHY_TIERS:
                add(
                    names.trophy_location_name("Normal", world, level, trophy),
                    f"{trophy.lower()}_trophy",
                    "Normal",
                    world,
                    level,
                    record,
                )
            if (world, level) in BONUS_STUMP_PIECE_LEVELS:
                add(names.stump_piece_location_name("Normal", world, level), "stump_piece", "Normal", world, level, record)

    for world in BONUS_WORLDS:
        for level in range(1, LEVELS_PER_WORLD[world] + 1):
            record = addresses.bonus_level_record("Hard", world, level)
            add(names.goal_location_name("Hard", world, level), "bonus_goal", "Hard", world, level, record)
            for trophy in TROPHY_TIERS:
                add(
                    names.trophy_location_name("Hard", world, level, trophy),
                    f"{trophy.lower()}_trophy",
                    "Hard",
                    world,
                    level,
                    record,
                )
            add(names.ant_location_name("Hard", world, level), "ant", "Hard", world, level, record)

    for index in range(1, 101):
        add(names.balance_board_location_name(index), "balance_board", level=index)

    return locations


LOCATION_TABLE: dict[str, LocationData] = {}
TROPHY_TIERS = ("Bronze", "Silver", "Gold", "Platinum")
BONUS_STUMP_PIECE_LEVELS = {
    ("WA", 1),
    ("WA", 3),
    ("WA", 6),
    ("WB", 1),
    ("WB", 3),
    ("WB", 5),
    ("WB", 6),
    ("WC", 1),
    ("WC", 3),
    ("WC", 5),
    ("WC", 6),
}

ALL_LOCATION_DATA = iter_campaign_stage_names()
LOCATION_NAME_TO_ID = {name: data.code for name, data in LOCATION_TABLE.items()}

location_name_groups = {
    "Goal": {name for name, data in LOCATION_TABLE.items() if data.category in {"goal", "bonus_goal"}},
    "Trophies": {name for name, data in LOCATION_TABLE.items() if data.category.endswith("_trophy")},
    "Bronze Trophies": {name for name, data in LOCATION_TABLE.items() if data.category == "bronze_trophy"},
    "Silver Trophies": {name for name, data in LOCATION_TABLE.items() if data.category == "silver_trophy"},
    "Gold Trophies": {name for name, data in LOCATION_TABLE.items() if data.category == "gold_trophy"},
    "Platinum Trophies": {name for name, data in LOCATION_TABLE.items() if data.category == "platinum_trophy"},
    "Green Gems": {name for name, data in LOCATION_TABLE.items() if data.category == "green_gem"},
    "Kororin Capsules": {name for name, data in LOCATION_TABLE.items() if data.category == "stump_piece"},
    "Ants": {name for name, data in LOCATION_TABLE.items() if data.category == "ant"},
    "Bonus Worlds": {name for name, data in LOCATION_TABLE.items() if data.world in BONUS_WORLDS},
    "Tutorials": {name for name, data in LOCATION_TABLE.items() if data.category == "tutorial"},
    "Wii Balance Board": {name for name, data in LOCATION_TABLE.items() if data.category == "balance_board"},
}


def trophy_category_enabled(world: MarbleBalanceWorld, category: str) -> bool:
    option = world.options.trophy_sanity.value
    return (
        option == TrophySanity.option_all
        or option == TrophySanity.option_bronze and category == "bronze_trophy"
        or option == TrophySanity.option_silver and category == "silver_trophy"
        or option == TrophySanity.option_gold and category == "gold_trophy"
        or option == TrophySanity.option_platinum and category == "platinum_trophy"
    )


def enabled_location_names(world: MarbleBalanceWorld) -> list[str]:
    selected: list[str] = []

    for name, data in LOCATION_TABLE.items():
        if data.category == "tutorial":
            if world.options.tutorial_checks:
                selected.append(name)
            continue

        if data.category == "counter_stump_unlock":
            required = world.options.required_stump_pieces_for_w7.value
            difficulty = "Hard" if world.options.goal.value == 1 else "Normal"
            if name == counter_stump_unlock_name(difficulty, required):
                selected.append(name)
            continue

        if data.category == "counter_hard_mode":
            required = world.options.required_green_gems_for_hard.value
            if "Hard" in world.enabled_difficulties and world.options.hard_mode_unlock.value == 2 and name == counter_hard_mode_name(required):
                selected.append(name)
            continue

        if data.category == "balance_board":
            if world.options.wii_balance_board_levels:
                selected.append(name)
            continue

        if data.world in BONUS_WORLDS:
            if data.difficulty == "Hard" and "Hard" not in world.enabled_difficulties:
                continue
            if data.category == "ant" and not world.options.anthony_sanity:
                continue
            if data.category.endswith("_trophy"):
                if trophy_category_enabled(world, data.category):
                    selected.append(name)
            else:
                selected.append(name)
            continue

        if data.difficulty not in world.enabled_difficulties:
            continue
        if data.world not in world.enabled_worlds_by_difficulty.get(data.difficulty, ()):
            continue
        if data.category == "green_gem" and not world.options.green_gem_sanity:
            continue
        if data.category == "ant" and not world.options.anthony_sanity:
            continue
        if data.category.endswith("_trophy") and not trophy_category_enabled(world, data.category):
            continue
        selected.append(name)

    return selected


def create_locations(world: MarbleBalanceWorld) -> None:
    for location_name in enabled_location_names(world):
        data = LOCATION_TABLE[location_name]
        region = world.region_for_location_data(data)
        region.locations.append(MarbleBalanceLocation(world.player, location_name, data.code, region))
