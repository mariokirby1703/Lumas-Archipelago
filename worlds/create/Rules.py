from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import CollectionState, LocationProgressType

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
    if (
        world.required_sparks > 0
        and world.spark_goal_mode == "goal_world_unlock"
        and world_key == world.goal_world_key
    ):
        return lambda state: _spark_count(state, world) >= world.required_sparks
    item_name = game_data.world_access_item_name(world_key)
    return lambda state: _has(state, world, item_name)


def _spark_count(state: CollectionState, world: CreateWorld) -> int:
    return sum(
        state.count(item_name, world.player) * amount
        for item_name, amount in SPARK_ITEM_AMOUNTS.items()
    )


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
    return _solvable_challenge_count(state, world, world_key) >= chain


def _challenge_rule(world: CreateWorld, challenge_data: game_data.ChallengeData):
    access_rule = _world_access_rule(world, challenge_data.world_key)
    required_object_groups = _challenge_logic_object_groups(world, challenge_data)
    required_completion_count = _required_completion_count(challenge_data.challenge)

    def rule(state: CollectionState) -> bool:
        return (
            access_rule(state)
            and any(
                all(_has(state, world, item_name) for item_name in required_objects)
                for required_objects in required_object_groups
            )
            and _has_world_completions(
                state,
                world,
                challenge_data.world_key,
                challenge_data.challenge,
                required_completion_count,
            )
        )

    return rule


def _challenge_logic_object_groups(
    world: CreateWorld,
    challenge_data: game_data.ChallengeData,
) -> tuple[tuple[str, ...], ...]:
    if challenge_data.world_key == world.starting_world_key and challenge_data.challenge == 1:
        possible_requirements = game_data.possible_challenge_requirements(challenge_data, 1)
        if possible_requirements:
            return tuple(
                tuple(game_data.object_item_name(object_name) for object_name in requirement.objects)
                for requirement in possible_requirements
            )
    return (
        tuple(
            game_data.object_item_name(object_name)
            for object_name in game_data.challenge_logic_object_names(challenge_data)
        ),
    )


def _possible_challenge_rule(world: CreateWorld, challenge_data: game_data.ChallengeData, spark: int | None):
    possible_requirements = game_data.possible_challenge_requirements(challenge_data, spark)
    if not possible_requirements:
        return None

    access_rule = _world_access_rule(world, challenge_data.world_key)
    required_completion_count = _required_completion_count(challenge_data.challenge)

    def rule(state: CollectionState) -> bool:
        return (
            access_rule(state)
            and any(
                all(_has(state, world, game_data.object_item_name(object_name)) for object_name in requirement.objects)
                for requirement in possible_requirements
            )
            and _has_world_completions(
                state,
                world,
                challenge_data.world_key,
                challenge_data.challenge,
                required_completion_count,
            )
        )

    return rule


def _challenge_objects_available(state: CollectionState, world: CreateWorld, challenge_data: game_data.ChallengeData) -> bool:
    return any(
        all(_has(state, world, item_name) for item_name in required_objects)
        for required_objects in _challenge_logic_object_groups(world, challenge_data)
    )


def _solvable_challenge_count(state: CollectionState, world: CreateWorld, world_key: str) -> int:
    access_rule = _world_access_rule(world, world_key)
    if not access_rule(state):
        return 0

    solved = 0
    changed = True
    solvable: set[int] = set()
    while changed:
        changed = False
        for challenge in range(1, 11):
            if challenge in solvable:
                continue
            challenge_data = game_data.CHALLENGE_TABLE[(world_key, challenge)]
            if (
                _challenge_objects_available(state, world, challenge_data)
                and _required_completion_count(challenge) <= solved
            ):
                solvable.add(challenge)
                solved += 1
                changed = True
    return solved


def set_entrance_rules(world: CreateWorld) -> None:
    for world_key in world.active_world_keys:
        entrance = world.get_entrance(f"Hub to {game_data.WORLD_NAMES[world_key]}")
        world.set_rule(entrance, _world_access_rule(world, world_key))


def set_location_rules(world: CreateWorld) -> None:
    for location in world.get_locations():
        data = Locations.LOCATION_TABLE[location.name]
        if data.category in {"challenge", "spark"} and data.world_key and data.challenge:
            challenge_data = game_data.CHALLENGE_TABLE[(data.world_key, data.challenge)]
            strict_rule = _challenge_rule(world, challenge_data)
            world.set_rule(location, strict_rule)
            possible_rule = _possible_challenge_rule(world, challenge_data, data.spark)
            if possible_rule is not None:
                location.possible_access_rule = possible_rule
                location.out_of_logic_possible = game_data.challenge_has_out_of_logic_possible(
                    challenge_data,
                    data.spark,
                )
                if getattr(world.multiworld, "generation_is_fake", False) and location.out_of_logic_possible:
                    location.progress_type = LocationProgressType.PRIORITY
                    world.set_rule(
                        location,
                        lambda state, strict_rule=strict_rule, possible_rule=possible_rule: (
                            strict_rule(state) or possible_rule(state)
                        ),
                    )
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
        spark_count = _spark_count(state, world)
        if world.required_sparks > 0 and world.spark_goal_mode == "spark_hunt":
            return spark_count >= world.required_sparks
        return state.has(ITEM_VICTORY, world.player) and spark_count >= world.required_sparks

    world.set_completion_rule(completion_rule)


def set_all_rules(world: CreateWorld) -> None:
    set_entrance_rules(world)
    set_location_rules(world)
    set_completion_condition(world)
