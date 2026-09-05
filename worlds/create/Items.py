from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification

from . import game_data
from .world_constants import (
    FILLER_ITEMS, GAME_NAME, ITEM_ID_BASE, ITEM_VICTORY, LIMITED_FILLER_ITEMS, LIMITED_FILLER_ITEM_NAMES,
    SPARK_ITEM_AMOUNTS, WORLD_KEYS,
)

if TYPE_CHECKING:
    from .world import CreateWorld


@dataclass(frozen=True)
class ItemData:
    code: int
    classification: ItemClassification


class CreateItem(Item):
    game = GAME_NAME


def build_item_table() -> dict[str, ItemData]:
    entries: list[tuple[str, ItemClassification]] = []
    entries.append((ITEM_VICTORY, ItemClassification.progression))
    for item_name in SPARK_ITEM_AMOUNTS:
        entries.append((item_name, ItemClassification.progression))
    for world_key in WORLD_KEYS:
        entries.append((game_data.world_access_item_name(world_key), ItemClassification.progression))
    required_values = game_data.required_object_values()
    for obj in game_data.UNLOCKABLE_OBJECTS:
        classification = (
            ItemClassification.progression_skip_balancing
            if obj.value in required_values
            else ItemClassification.useful
        )
        entries.append((game_data.object_item_name(obj.name), classification))
    for filler in FILLER_ITEMS:
        entries.append((filler, ItemClassification.filler))
    for filler in dict.fromkeys(LIMITED_FILLER_ITEMS):
        entries.append((filler, ItemClassification.filler))

    return {
        name: ItemData(ITEM_ID_BASE + index, classification)
        for index, (name, classification) in enumerate(entries, start=1)
    }


ITEM_TABLE = build_item_table()
ITEM_NAME_TO_ID = {name: data.code for name, data in ITEM_TABLE.items()}

item_groups = {
    "World Access": {game_data.world_access_item_name(world_key) for world_key in WORLD_KEYS},
    "Objects": {game_data.object_item_name(obj.name) for obj in game_data.UNLOCKABLE_OBJECTS},
    "Sparks": set(SPARK_ITEM_AMOUNTS),
    "Filler": set(FILLER_ITEMS) | set(LIMITED_FILLER_ITEM_NAMES),
}


def create_item(world: CreateWorld, name: str) -> CreateItem:
    data = ITEM_TABLE[name]
    return CreateItem(name, _classification_for_world(world, name), data.code, world.player)


def _classification_for_world(world: CreateWorld, name: str) -> ItemClassification:
    if name in FILLER_ITEMS or name in LIMITED_FILLER_ITEM_NAMES:
        return ItemClassification.filler
    if name == ITEM_VICTORY or name in SPARK_ITEM_AMOUNTS:
        return ItemClassification.progression_skip_balancing
    if name in item_groups["World Access"]:
        return ItemClassification.progression

    object_data = game_data.UNLOCKABLE_OBJECTS_BY_NAME.get(name)
    if object_data is None:
        return ITEM_TABLE[name].classification
    # Item-link groups create a proxy world before generate_early() initializes
    # active_world_keys. Use the complete world set for that proxy; Archipelago
    # merges the classifications of the linked player items afterwards.
    active_world_keys = getattr(world, "active_world_keys", WORLD_KEYS)
    if object_data.value in game_data.required_object_values(active_world_keys):
        return ItemClassification.progression
    return ItemClassification.useful


def create_all_items(world: CreateWorld) -> None:
    items: list[CreateItem] = []
    precollected = Counter(item.name for item in world.multiworld.precollected_items[world.player])
    reserved = Counter(
        location.item.name
        for location in world.multiworld.get_locations(world.player)
        if location.item is not None and location.item.player == world.player
    )

    def already_reserved(item_name: str) -> bool:
        if precollected[item_name] <= 0:
            if reserved[item_name] <= 0:
                return False
            reserved[item_name] -= 1
            return True
        precollected[item_name] -= 1
        return True

    spark_unlocks_goal_world = world.required_sparks > 0 and world.spark_goal_mode == "goal_world_unlock"

    for world_key in world.active_world_keys:
        if spark_unlocks_goal_world and world_key == world.goal_world_key:
            continue
        item_name = game_data.world_access_item_name(world_key)
        if not already_reserved(item_name):
            items.append(world.create_item(item_name))

    for obj in game_data.UNLOCKABLE_OBJECTS:
        item_name = game_data.object_item_name(obj.name)
        if not already_reserved(item_name):
            items.append(world.create_item(item_name))

    unfilled_locations = len(world.multiworld.get_unfilled_locations(world.player))
    spark_capacity = max(0, unfilled_locations - len(items))
    capped_required_sparks = min(world.required_sparks, 610)
    while capped_required_sparks > 0:
        try:
            spark_amounts = game_data.spark_item_amounts_for_total(capped_required_sparks, world.random, spark_capacity)
        except ValueError:
            capped_required_sparks -= 1
            continue
        if len(spark_amounts) <= spark_capacity:
            break
        capped_required_sparks -= 1
    else:
        spark_amounts = []
    world.required_sparks = capped_required_sparks
    for amount in spark_amounts:
        items.append(world.create_item(game_data.spark_item_name(amount)))

    # Always aim for a full 50% safety margin. Round upward so even a small
    # non-zero requirement receives at least one extra Spark when a slot exists.
    desired_extra_sparks = min(610 - world.required_sparks, ceil(world.required_sparks * 0.5))
    extra_spark_cap = desired_extra_sparks
    extra_spark_capacity = max(0, unfilled_locations - len(items))
    extra_spark_amounts: list[int] = []
    while extra_spark_cap > 0 and len(extra_spark_amounts) < extra_spark_capacity:
        try:
            candidate_amounts = game_data.spark_item_amounts_for_total(
                extra_spark_cap,
                world.random,
                extra_spark_capacity - len(extra_spark_amounts),
            )
        except ValueError:
            extra_spark_cap -= 1
            continue
        if len(candidate_amounts) <= extra_spark_capacity - len(extra_spark_amounts):
            extra_spark_amounts = candidate_amounts
            break
        extra_spark_cap -= 1
    for amount in extra_spark_amounts:
        item = world.create_item(game_data.spark_item_name(amount))
        item.classification = ItemClassification.useful
        items.append(item)
    world.extra_sparks = sum(extra_spark_amounts)

    minimum_extra_slots = ceil(desired_extra_sparks / max(SPARK_ITEM_AMOUNTS.values()))
    if extra_spark_capacity >= minimum_extra_slots and world.extra_sparks != desired_extra_sparks:
        raise RuntimeError(
            f"Create could fit the requested {desired_extra_sparks} extra Sparks, "
            f"but generated only {world.extra_sparks}."
        )

    if len(items) > unfilled_locations:
        raise ValueError(
            f"Create item pool has {len(items)} progression items but only {unfilled_locations} open locations."
        )

    limited_fillers = [name for name in LIMITED_FILLER_ITEMS if not already_reserved(name)]
    world.random.shuffle(limited_fillers)
    limited_filler_slots = min(len(limited_fillers), unfilled_locations - len(items))
    items.extend(world.create_item(name) for name in limited_fillers[:limited_filler_slots])

    items.extend(world.create_filler() for _ in range(unfilled_locations - len(items)))
    world.multiworld.itempool += items
