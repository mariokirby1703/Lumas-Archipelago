from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification

from .Names import item_names as names
from .Options import HardModeUnlock
from .Options import Goal
from .world_constants import (
    DIFFICULTIES,
    FIGURE_ROLLER_HEADS,
    ITEM_ID_BASE,
    JUNK_ITEMS,
    LEVELS_PER_WORLD,
    MARBLES,
    BONUS_WORLDS,
    NORMAL_WORLDS,
    TRAPS,
    VEHICLE_PARTS,
    GAME_NAME,
)

if TYPE_CHECKING:
    from .world import MarbleBalanceWorld


@dataclass(frozen=True)
class ItemData:
    code: int
    classification: ItemClassification


class MarbleBalanceItem(Item):
    game = GAME_NAME


def build_item_table() -> dict[str, ItemData]:
    item_names: list[tuple[str, ItemClassification]] = [
        (names.GREEN_GEM, ItemClassification.progression),
        (names.STUMP_TEMPLE_PIECE, ItemClassification.progression),
        (names.HARD_MODE, ItemClassification.progression),
        (names.SUBMARINE, ItemClassification.progression),
        (names.ROCKET_SHIP, ItemClassification.progression),
        (names.VICTORY, ItemClassification.progression),
    ]

    for difficulty in DIFFICULTIES:
        for normal_world in NORMAL_WORLDS:
            item_names.append((names.world_access_name(difficulty, normal_world), ItemClassification.progression))

    for bonus_world in BONUS_WORLDS:
        for level in range(1, LEVELS_PER_WORLD[bonus_world] + 1):
            item_names.append((names.bonus_level_unlock_name("Normal", bonus_world, level), ItemClassification.progression))
            item_names.append((names.bonus_level_unlock_name("Hard", bonus_world, level), ItemClassification.progression))

    for marble in MARBLES:
        item_names.append((names.marble_name(marble), ItemClassification.useful))

    for head in FIGURE_ROLLER_HEADS:
        item_names.append((names.head_name(head), ItemClassification.useful))

    for junk in JUNK_ITEMS:
        item_names.append((names.junk_name(junk), ItemClassification.filler))

    for part in VEHICLE_PARTS:
        item_names.append((names.vehicle_part_name(part), ItemClassification.progression))

    for trap in TRAPS:
        item_names.append((trap, ItemClassification.trap))

    return {
        item_name: ItemData(ITEM_ID_BASE + index, classification)
        for index, (item_name, classification) in enumerate(item_names, start=1)
    }


ITEM_TABLE = build_item_table()
ITEM_NAME_TO_ID = {name: data.code for name, data in ITEM_TABLE.items()}

item_groups = {
    "World Access": {
        names.world_access_name(difficulty, world) for difficulty in DIFFICULTIES for world in NORMAL_WORLDS
    },
    "Bonus Level Access": {
        names.bonus_level_unlock_name(difficulty, world, level)
        for difficulty in ("Normal", "Hard")
        for world in BONUS_WORLDS
        for level in range(1, LEVELS_PER_WORLD[world] + 1)
    },
    "Vehicles": {names.SUBMARINE, names.ROCKET_SHIP} | {names.vehicle_part_name(part) for part in VEHICLE_PARTS},
    "Marbles": {names.marble_name(marble) for marble in MARBLES},
    "Figure Roller Heads": {names.head_name(head) for head in FIGURE_ROLLER_HEADS},
    "Junk": {names.junk_name(junk) for junk in JUNK_ITEMS},
    "Traps": set(TRAPS),
}


def create_item(world: MarbleBalanceWorld, name: str) -> MarbleBalanceItem:
    data = ITEM_TABLE[name]
    classification = data.classification
    if name == names.GREEN_GEM and world.options.hard_mode_unlock != HardModeUnlock.option_green_gems:
        classification = ItemClassification.useful
    return MarbleBalanceItem(name, classification, data.code, world.player)


def trap_weight(world: MarbleBalanceWorld, trap: str) -> int:
    weight_values = {0: 1, 1: 2, 2: 4}
    option_by_trap = {
        "Blackout Trap": world.options.blackout_trap_weight,
        "Mirror Trap": world.options.mirror_trap_weight,
        "Inverse Trap": world.options.inverse_trap_weight,
        "Noclip Trap": world.options.noclip_trap_weight,
    }
    return weight_values[option_by_trap[trap].value]


def get_filler_item_name(world: MarbleBalanceWorld) -> str:
    if world.random.randint(1, 100) <= world.options.trap_chance.value:
        return world.random.choices(TRAPS, weights=[trap_weight(world, trap) for trap in TRAPS], k=1)[0]
    return names.junk_name(world.random.choice(JUNK_ITEMS))


def extra_requirement_item_count(required: int, extra_percentage: int) -> int:
    return (required * extra_percentage + 99) // 100


def extend_until_full(
    items: list[MarbleBalanceItem],
    candidates: list[MarbleBalanceItem],
    location_count: int,
) -> None:
    remaining_space = location_count - len(items)
    if remaining_space > 0:
        items.extend(candidates[:remaining_space])


def create_required_items(world: MarbleBalanceWorld, location_count: int) -> list[MarbleBalanceItem]:
    items: list[MarbleBalanceItem] = []
    stump_locked_difficulty = "Hard" if world.options.goal == Goal.option_stump_temple_level_10_hard else "Normal"

    for difficulty in world.enabled_difficulties:
        for normal_world in NORMAL_WORLDS[:6]:
            if world.starting_worlds_by_difficulty.get(difficulty) == normal_world:
                continue
            items.append(world.create_item(names.world_access_name(difficulty, normal_world)))

    vehicle_difficulties = {"Easy", "Normal"} & set(world.enabled_difficulties)
    if world.options.split_vehicle_world_access and vehicle_difficulties and any(
        "W5" in world.enabled_worlds_by_difficulty[difficulty] for difficulty in vehicle_difficulties
    ):
        items.append(world.create_item(names.SUBMARINE))
    if world.options.split_vehicle_world_access and vehicle_difficulties and any(
        "W6" in world.enabled_worlds_by_difficulty[difficulty] for difficulty in vehicle_difficulties
    ):
        items.append(world.create_item(names.ROCKET_SHIP))

    if world.uses_hard_mode_item:
        items.append(world.create_item(names.HARD_MODE))

    extra_counter_percentage = world.options.extra_counter_item_percentage.value

    for _ in range(world.options.required_stump_pieces_for_w7.value):
        items.append(world.create_item(names.STUMP_TEMPLE_PIECE))

    for difficulty in world.enabled_difficulties:
        if difficulty != stump_locked_difficulty:
            if world.starting_worlds_by_difficulty.get(difficulty) == "W7":
                continue
            items.append(world.create_item(names.world_access_name(difficulty, "W7")))

    if world.options.hard_mode_unlock == HardModeUnlock.option_green_gems:
        for _ in range(world.options.required_green_gems_for_hard.value):
            items.append(world.create_item(names.GREEN_GEM))

    for bonus_world in BONUS_WORLDS:
        for level in range(1, LEVELS_PER_WORLD[bonus_world] + 1):
            if not (world.starting_worlds_by_difficulty.get("Normal") == bonus_world and level <= 5):
                items.append(world.create_item(names.bonus_level_unlock_name("Normal", bonus_world, level)))
            if "Hard" in world.enabled_difficulties and not (
                world.starting_worlds_by_difficulty.get("Hard") == bonus_world and level <= 5
            ):
                items.append(world.create_item(names.bonus_level_unlock_name("Hard", bonus_world, level)))

    starting_marble = world.starting_marble or world.random.choice(MARBLES)
    world.starting_marble = starting_marble
    world.push_precollected(world.create_item(names.marble_name(starting_marble)))

    optional_items: list[MarbleBalanceItem] = []
    for _ in range(extra_requirement_item_count(world.options.required_stump_pieces_for_w7.value, extra_counter_percentage)):
        optional_items.append(world.create_item(names.STUMP_TEMPLE_PIECE))

    if world.options.hard_mode_unlock == HardModeUnlock.option_green_gems:
        for _ in range(extra_requirement_item_count(world.options.required_green_gems_for_hard.value, extra_counter_percentage)):
            optional_items.append(world.create_item(names.GREEN_GEM))

    for marble in MARBLES:
        if marble != starting_marble:
            optional_items.append(world.create_item(names.marble_name(marble)))

    for head in FIGURE_ROLLER_HEADS:
        optional_items.append(world.create_item(names.head_name(head)))

    extend_until_full(items, optional_items, location_count)

    return items


def create_all_items(world: MarbleBalanceWorld) -> None:
    unfilled_locations = len(world.multiworld.get_unfilled_locations(world.player))
    itempool = create_required_items(world, unfilled_locations)
    itempool += [world.create_filler() for _ in range(unfilled_locations - len(itempool))]
    world.multiworld.itempool += itempool
