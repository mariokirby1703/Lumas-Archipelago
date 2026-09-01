from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import CollectionState

from . import Locations, game_data
from .world_constants import HUB_WORLD_KEY, ITEM_VICTORY, SPARK_ITEM_AMOUNTS

if TYPE_CHECKING:
    from .world import CreateWorld


def _has(state: CollectionState, world: CreateWorld, item: str) -> bool:
    return state.has(item, world.player)


def _world_access_rule(world: CreateWorld, world_key: str):
    if world_key == HUB_WORLD_KEY:
        return lambda state: True
    if world_key == world.starting_world_key:
        return lambda state: True
    item_name = game_data.world_access_item_name(world_key)
    return lambda state: _has(state, world, item_name)


def _challenge_completion_name(world: CreateWorld, world_key: str, challenge: int) -> str:
    return game_data.spark_location_name(world_key, challenge, 1)


def _required_completion_count(challenge: int) -> int:
    return max(0, challenge - 3)


def _has_world_completions(
    state: CollectionState,
    world: CreateWorld,
    world_key: str,
    current_challenge: int,
    count: int,
) -> bool:
    if count <= 0:
        return True
    completion_locations = [
        _challenge_completion_name(world, world_key, challenge)
        for challenge in range(1, current_challenge)
    ]
    reachable_count = sum(
        1
        for location_name in completion_locations
        if state.can_reach(location_name, "Location", world.player)
    )
    return reachable_count >= count


def _has_create_chain_challenge_progress(state: CollectionState, world: CreateWorld, world_key: str, chain: int) -> bool:
    if chain <= 1:
        return True
    return _has_world_completions(state, world, world_key, 11, chain)


def _challenge_rule(world: CreateWorld, challenge_data: game_data.ChallengeData):
    access_rule = _world_access_rule(world, challenge_data.world_key)
    required_objects = tuple(
        game_data.object_item_name(requirement.name)
        for requirement in challenge_data.objects
        if requirement.global_value in game_data.UNLOCKABLE_OBJECT_VALUES
    )
    required_completion_count = _required_completion_count(challenge_data.challenge)

    def rule(state: CollectionState) -> bool:
        return (
            access_rule(state)
            and all(_has(state, world, item_name) for item_name in required_objects)
            and _has_world_completions(
                state,
                world,
                challenge_data.world_key,
                challenge_data.challenge,
                required_completion_count,
            )
        )

    return rule


def set_entrance_rules(world: CreateWorld) -> None:
    for world_key in world.active_world_keys:
        entrance = world.get_entrance(f"Hub to {game_data.WORLD_NAMES[world_key]}")
        world.set_rule(entrance, _world_access_rule(world, world_key))


def set_location_rules(world: CreateWorld) -> None:
    for location in world.get_locations():
        data = Locations.LOCATION_TABLE[location.name]
        if data.category in {"challenge", "spark"} and data.world_key and data.challenge:
            challenge_data = game_data.CHALLENGE_TABLE[(data.world_key, data.challenge)]
            world.set_rule(location, _challenge_rule(world, challenge_data))
        elif data.category == "create_chain" and data.world_key:
            access_rule = _world_access_rule(world, data.world_key)
            chain = data.chain or 1
            world.set_rule(
                location,
                lambda state, access_rule=access_rule, world_key=data.world_key, chain=chain: (
                    access_rule(state)
                    and _has_create_chain_challenge_progress(state, world, world_key, chain)
                ),
            )


def set_completion_condition(world: CreateWorld) -> None:
    def completion_rule(state: CollectionState) -> bool:
        spark_count = sum(
            state.count(item_name, world.player) * amount
            for item_name, amount in SPARK_ITEM_AMOUNTS.items()
        )
        return state.has(ITEM_VICTORY, world.player) and spark_count >= world.required_sparks

    world.set_completion_rule(completion_rule)


def set_all_rules(world: CreateWorld) -> None:
    set_entrance_rules(world)
    set_location_rules(world)
    set_completion_condition(world)
