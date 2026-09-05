from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from BaseClasses import Location

from . import game_data
from .world_constants import (
    CREATE_CHAINS_PER_WORLD,
    GAME_NAME,
    LOCATION_ID_BASE,
    WORLD_KEYS,
)

if TYPE_CHECKING:
    from .world import CreateWorld


@dataclass(frozen=True)
class LocationData:
    code: int
    category: str
    world_key: str | None = None
    challenge: int | None = None
    spark: int | None = None
    chain: int | None = None


class CreateLocation(Location):
    game = GAME_NAME


def build_location_table() -> dict[str, LocationData]:
    table: dict[str, LocationData] = {}
    next_id = LOCATION_ID_BASE + 1

    def add(name: str, category: str, world_key: str | None = None, challenge: int | None = None,
            spark: int | None = None, chain: int | None = None) -> None:
        nonlocal next_id
        table[name] = LocationData(next_id, category, world_key, challenge, spark, chain)
        next_id += 1

    for challenge_data in (game_data.HUB_CHALLENGE_DATA, *game_data.ALL_CHALLENGES):
        add(
            game_data.challenge_location_name(challenge_data.world_key, challenge_data.challenge),
            "challenge",
            challenge_data.world_key,
            challenge_data.challenge,
        )
        for spark in range(1, challenge_data.spark_reward + 1):
            add(
                game_data.spark_location_name(challenge_data.world_key, challenge_data.challenge, spark),
                "spark",
                challenge_data.world_key,
                challenge_data.challenge,
                spark,
            )

    add(game_data.hub_create_chain_location_name(), "create_chain", chain=1)
    add("Starting World Unlock", "starting_world_unlock")
    add("Spark Requirement Met", "spark_goal_world_unlock")
    for world_key in WORLD_KEYS:
        for chain in range(1, CREATE_CHAINS_PER_WORLD + 1):
            add(game_data.create_chain_location_name(world_key, chain), "create_chain", world_key, chain=chain)
    return table


LOCATION_TABLE = build_location_table()
LOCATION_NAME_TO_ID = {name: data.code for name, data in LOCATION_TABLE.items()}

location_name_groups = {
    "Challenges": {name for name, data in LOCATION_TABLE.items() if data.category == "challenge"},
    "Sparks": {name for name, data in LOCATION_TABLE.items() if data.category == "spark"},
    "Create Chains": {name for name, data in LOCATION_TABLE.items() if data.category == "create_chain"},
}


def enabled_location_names(world: CreateWorld) -> list[str]:
    locations: list[str] = []
    for name, data in LOCATION_TABLE.items():
        if data.world_key is not None and data.world_key != game_data.HUB_WORLD_KEY and data.world_key not in world.active_world_keys:
            continue
        if data.category == "spark":
            locations.append(name)
        elif data.category == "create_chain" and (data.world_key is None or world.options.create_chain_checks):
            locations.append(name)
        elif data.category == "starting_world_unlock":
            locations.append(name)
        elif (
            data.category == "spark_goal_world_unlock"
            and world.required_sparks > 0
            and world.spark_goal_mode == "goal_world_unlock"
        ):
            locations.append(name)
    return locations


def create_locations(world: CreateWorld) -> None:
    for location_name in enabled_location_names(world):
        data = LOCATION_TABLE[location_name]
        region = world.region_for_location_data(data)
        location = CreateLocation(world.player, location_name, data.code, region)
        region.locations.append(location)
