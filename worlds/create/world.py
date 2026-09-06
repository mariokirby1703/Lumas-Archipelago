from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from BaseClasses import Item, ItemClassification, Region
from worlds.AutoWorld import World

from . import Items, Locations, Regions, Rules, game_data, web_world
from .Options import CreateOptions
from .world_constants import (
    FILLER_ITEMS, FIRST_TEN_WORLDS, GAME_NAME, HUB_WORLD_KEY, ITEM_UT_GLITCHED, ITEM_VICTORY,
    SPARK_ITEM_AMOUNTS, WORLD_KEYS,
)


class CreateWorld(World):
    """
    Create is a physics puzzle sandbox where Archipelago controls world access and object ownership.
    The Dolphin client reads challenge Sparks and Create Chains from RAM, then enforces received AP items live.
    """

    game = GAME_NAME
    web = web_world.CreateWebWorld()
    options_dataclass = CreateOptions
    options: CreateOptions

    item_name_to_id = Items.ITEM_NAME_TO_ID
    location_name_to_id = Locations.LOCATION_NAME_TO_ID
    item_name_groups = Items.item_groups
    location_name_groups = Locations.location_name_groups
    glitches_item_name = ITEM_UT_GLITCHED

    item_type = Items.CreateItem
    location_type = Locations.CreateLocation

    topology_present = False
    ut_can_gen_without_yaml = True

    starting_world_key: str
    goal_world_key: str | None
    active_location_names: list[str]
    active_world_keys: tuple[str, ...]
    world_unlock_order: tuple[str, ...]
    required_sparks: int
    extra_sparks: int
    spark_goal_mode: str

    @staticmethod
    def interpret_slot_data(slot_data: dict[str, Any]) -> dict[str, Any]:
        return slot_data

    def generate_early(self) -> None:
        self._apply_ut_slot_data()
        self.required_sparks = int(self.options.required_sparks.value)
        self.extra_sparks = 0
        self.spark_goal_mode = (
            "spark_hunt"
            if self.required_sparks > 0 and self.options.spark_goal_mode.value == 1
            else "goal_world_unlock"
        )
        active_world_keys = list(WORLD_KEYS if self.options.include_ii_worlds else FIRST_TEN_WORLDS)
        if not getattr(self, "starting_world_key", None):
            starting_option = self.options.starting_world.value
            self.starting_world_key = (
                self.random.choice(active_world_keys)
                if starting_option == 0
                else WORLD_KEYS[starting_option - 1]
            )
        if self.spark_goal_mode == "spark_hunt":
            # Goal World is deliberately ignored in Spark Hunt. Do not even
            # consume an RNG choice for it, so changing the option cannot alter
            # the generated seed.
            self.goal_world_key = None
        elif not getattr(self, "goal_world_key", None):
            goal_option = self.options.goal_world.value
            self.goal_world_key = (
                self.random.choice(active_world_keys)
                if goal_option == 0
                else WORLD_KEYS[goal_option - 1]
            )

        selected_world_keys = [self.starting_world_key]
        if self.goal_world_key is not None:
            selected_world_keys.append(self.goal_world_key)
        for selected_world_key in selected_world_keys:
            if selected_world_key not in active_world_keys:
                active_world_keys.append(selected_world_key)
        self.active_world_keys = tuple(active_world_keys)

        if not self._can_bootstrap_starting_world(self.starting_world_key):
            bootstrap_worlds = [
                world_key for world_key in self.active_world_keys
                if self._can_bootstrap_starting_world(world_key)
            ]
            self.starting_world_key = self.random.choice(bootstrap_worlds)
        if self.goal_world_key is not None and self.goal_world_key not in self.active_world_keys:
            self.goal_world_key = self.random.choice(self.active_world_keys)
        if (
            self.required_sparks > 0
            and self.spark_goal_mode == "goal_world_unlock"
            and self.goal_world_key == self.starting_world_key
        ):
            possible_goal_worlds = [
                world_key for world_key in self.active_world_keys
                if world_key != self.starting_world_key
            ]
            self.goal_world_key = self.random.choice(possible_goal_worlds)
        remaining_worlds = [world_key for world_key in self.active_world_keys if world_key != self.starting_world_key]
        self.random.shuffle(remaining_worlds)
        self.world_unlock_order = (self.starting_world_key, *remaining_worlds)

    def _apply_ut_slot_data(self) -> None:
        re_gen_passthrough = getattr(self.multiworld, "re_gen_passthrough", {})
        slot_data = re_gen_passthrough.get(self.game)
        if not slot_data:
            return

        for key, value in slot_data.get("options", {}).items():
            option = getattr(self.options, key, None)
            if option is not None:
                setattr(self.options, key, option.from_any(value))

        starting_world = slot_data.get("starting_world")
        if isinstance(starting_world, str) and starting_world in WORLD_KEYS:
            self.starting_world_key = starting_world

        goal_world = slot_data.get("goal_world")
        if isinstance(goal_world, str) and goal_world in WORLD_KEYS:
            self.goal_world_key = goal_world

    def create_regions(self) -> None:
        Regions.create_and_connect_regions(self)
        Locations.create_locations(self)
        self._place_victory_item()
        self._place_bootstrap_items()
        self.active_location_names = [location.name for location in self.get_locations()]

    def create_items(self) -> None:
        Items.create_all_items(self)

    def set_rules(self) -> None:
        Rules.set_all_rules(self)

    def fill_hook(
        self,
        progitempool: list[Item],
        usefulitempool: list[Item],
        filleritempool: list[Item],
        fill_locations: list,
    ) -> None:
        create_groups = {
            group_id: group for group_id, group in self.multiworld.groups.items()
            if group["game"] == self.game
        }
        if create_groups:
            linked_players = set().union(*(group["players"] for group in create_groups.values()))
            if self.player not in linked_players or self.player != min(linked_players):
                return
            self._sphere_fill_create_progression(
                progitempool,
                fill_locations,
                recipient_ids=linked_players | set(create_groups),
                location_player_ids=set(self.multiworld.player_ids),
            )
            return
        if self.multiworld.players > 1:
            return
        self._sphere_fill_create_progression(progitempool, fill_locations)

    def _sphere_fill_create_progression(
        self,
        progitempool: list[Item],
        fill_locations: list,
        recipient_ids: set[int] | None = None,
        location_player_ids: set[int] | None = None,
    ) -> None:
        progression_names = Items.item_groups["Objects"] | Items.item_groups["World Access"]
        recipient_ids = recipient_ids or {self.player}
        location_player_ids = location_player_ids or {self.player}
        create_progression = [
            item for item in progitempool
            if item.player in recipient_ids and item.name in progression_names
        ]
        spark_progression = [
            item for item in progitempool
            if item.player in recipient_ids and item.name in SPARK_ITEM_AMOUNTS
        ]
        if not create_progression:
            return

        state = self.multiworld.state.copy()
        state.sweep_for_advancements()

        while create_progression:
            best_bundle: list[Item] | None = None
            best_locations: list | None = None
            best_score = -1
            candidate_bundles: list[list[Item]] = [[item] for item in create_progression]
            items_by_name = {item.name: item for item in create_progression}
            seen_bundles = {(item.name,) for item in create_progression}
            for world_key in self.active_world_keys:
                for challenge in range(1, 11):
                    challenge_data = game_data.CHALLENGE_TABLE[(world_key, challenge)]
                    for required_names in Rules._challenge_logic_object_groups(self, challenge_data):
                        bundle = [items_by_name[name] for name in required_names if name in items_by_name]
                        bundle_key = tuple(sorted(item.name for item in bundle))
                        if len(bundle) > 1 and bundle_key not in seen_bundles:
                            candidate_bundles.append(bundle)
                            seen_bundles.add(bundle_key)

            # A spark-gated goal world needs a whole threshold, not one Spark,
            # before an access-rule score can improve.
            if spark_progression and self.required_sparks > 0:
                spark_bundle: list[Item] = []
                spark_total = Rules._spark_count(state, self)
                for spark_item in sorted(
                    spark_progression, key=lambda item: SPARK_ITEM_AMOUNTS[item.name], reverse=True
                ):
                    spark_bundle.append(spark_item)
                    spark_total += SPARK_ITEM_AMOUNTS[spark_item.name]
                    if spark_total >= self.required_sparks:
                        candidate_bundles.append(spark_bundle)
                        break

            reachable_slots = sum(
                1 for location in fill_locations
                if location.player in location_player_ids and location.can_reach(state)
            )
            for bundle in candidate_bundles:
                valid_locations = [
                    location for location in fill_locations
                    if location.player in location_player_ids
                    and all(location.can_fill(state, item, check_access=True) for item in bundle)
                ]
                if not valid_locations or len(bundle) > reachable_slots:
                    continue
                if len(valid_locations) < len(bundle):
                    continue
                locations = self.random.sample(valid_locations, len(bundle))
                simulated_state = state.copy()
                for bundled_item, location in zip(bundle, locations):
                    simulated_state.collect(bundled_item, True, location)
                simulated_state.sweep_for_advancements()
                score = sum(
                    1 for candidate in fill_locations
                    if candidate.player in location_player_ids and candidate.can_reach(simulated_state)
                ) - len(bundle)
                if score > best_score:
                    best_bundle = bundle
                    best_locations = locations
                    best_score = score

            if best_bundle is None or best_locations is None:
                unplaced = ", ".join(item.name for item in create_progression)
                raise RuntimeError(f"Create sphere fill could not place progression items: {unplaced}")

            for item, location in zip(best_bundle, best_locations):
                self.multiworld.push_item(location, item, False)
                fill_locations.remove(location)
                progitempool.remove(item)
                if item in create_progression:
                    create_progression.remove(item)
                else:
                    spark_progression.remove(item)
                state.collect(item, True, location)
            state.sweep_for_advancements()

    def create_item(self, name: str) -> Items.CreateItem:
        if name == ITEM_UT_GLITCHED:
            return Items.CreateItem(name, ItemClassification.progression, None, self.player)
        return Items.create_item(self, name)

    def collect_item(self, state, item: Item, remove: bool = False) -> str | None:
        if item.player == self.player and ItemClassification.progression in item.classification:
            return item.name
        return super().collect_item(state, item, remove)

    def get_filler_item_name(self) -> str:
        return self.random.choice(FILLER_ITEMS)

    def region_for_location_data(self, data: Locations.LocationData) -> Region:
        if data.world_key is None:
            return self.get_region(Regions.HUB)
        return self.get_region(game_data.region_name(data.world_key))

    def _goal_location_name(self) -> str:
        assert self.goal_world_key is not None
        return game_data.spark_location_name(self.goal_world_key, 10, 1)

    def _place_victory_item(self) -> None:
        if self.spark_goal_mode == "spark_hunt":
            return
        self.get_location(self._goal_location_name()).place_locked_item(self.create_item(ITEM_VICTORY))

    def _starting_challenge_object_names(self, world_key: str) -> list[str]:
        challenge_data = game_data.CHALLENGE_TABLE[(world_key, 1)]
        return [
            game_data.object_item_name(requirement.name)
            for requirement in challenge_data.objects
            if requirement.global_value in game_data.UNLOCKABLE_OBJECT_VALUES
        ]

    def _can_bootstrap_starting_world(self, world_key: str) -> bool:
        return True

    def _place_bootstrap_items(self) -> None:
        self.get_location("Starting World Unlock").place_locked_item(
            self.create_item(game_data.world_access_item_name(self.starting_world_key))
        )
        if self.required_sparks > 0 and self.spark_goal_mode == "goal_world_unlock":
            assert self.goal_world_key is not None
            self.get_location("Spark Requirement Met").place_locked_item(
                self.create_item(game_data.world_access_item_name(self.goal_world_key))
            )
        if self.multiworld.players > 1:
            return
        bootstrap_locations: list[str] = []
        if self.options.create_chain_checks:
            bootstrap_locations.append(game_data.create_chain_location_name(self.starting_world_key, 1))
        bootstrap_locations.extend(
            [
                game_data.hub_create_chain_location_name(),
                game_data.spark_location_name(HUB_WORLD_KEY, 1, 1),
            ]
        )

        bootstrap_locations.extend(f"Hub World Create Chain Part {part}" for part in range(1, 4))

        bootstrap_items = ["Jumbo Ramp"]
        bootstrap_items.extend(
            item_name for item_name in self._starting_challenge_object_names(self.starting_world_key)
            if item_name != "Jumbo Ramp"
        )

        if len(bootstrap_items) > len(bootstrap_locations):
            candidates = [
                list(dict.fromkeys(("Jumbo Ramp", *group)))
                for challenge in range(1, 4)
                for group in game_data.challenge_logic_object_groups(
                    game_data.CHALLENGE_TABLE[(self.starting_world_key, challenge)], 1
                )
            ]
            candidates = [items for items in candidates if len(items) <= len(bootstrap_locations)]
            if not candidates:
                raise ValueError("Starting world has no opening route that fits the Hub checks.")
            bootstrap_items = min(candidates, key=len)

        for location_name, item_name in zip(bootstrap_locations, bootstrap_items):
            location = self.get_location(location_name)
            if location.item is None:
                location.place_locked_item(self.create_item(item_name))


    def fill_slot_data(self) -> Mapping[str, Any]:
        option_data = self.options.as_dict(
            "starting_world",
            "goal_world",
            "create_chain_checks",
            "include_ii_worlds",
            "required_sparks",
            "spark_goal_mode",
        )
        return {
            "game": self.game,
            "seed_name": self.multiworld.seed_name,
            "player_name": self.multiworld.get_player_name(self.player),
            "starting_world": self.starting_world_key,
            "goal_world": self.goal_world_key,
            "active_worlds": list(self.active_world_keys),
            "world_unlock_order": list(self.world_unlock_order),
            "starting_objects": self._starting_challenge_object_names(self.starting_world_key),
            "required_sparks": self.required_sparks,
            "extra_sparks": self.extra_sparks,
            "spark_goal_mode": self.spark_goal_mode,
            "options": option_data,
            "locations": {
                name: self._slot_location_data(name)
                for name in self.active_location_names
            },
            "worlds": {
                world_key: {
                    "name": game_data.WORLD_NAMES[world_key],
                    "access_item": game_data.world_access_item_name(world_key),
                    "hub_index": index,
                    "included": world_key in self.active_world_keys,
                }
                for index, world_key in enumerate(WORLD_KEYS)
            },
            "objects": {
                game_data.object_item_name(obj.name): {
                    "name": obj.name,
                    "global_value": obj.value,
                }
                for obj in game_data.UNLOCKABLE_OBJECTS
            },
            "challenges": {
                f"{challenge.world_key}:{challenge.challenge}": self._slot_challenge_data(challenge)
                for challenge in (game_data.HUB_CHALLENGE_DATA, *game_data.ALL_CHALLENGES)
            },
            "ram": {
                "addresses": game_data.RAM_ADDRESSES,
                "challenge_records": game_data.CHALLENGE_RECORDS,
                "ii_world_flags": game_data.II_WORLD_FLAGS_BY_NAME,
                "object_system": game_data.RAM_MAP["object_system"],
                "confirmed_current_world_ids": game_data.CONFIRMED_CURRENT_WORLD_IDS,
                "expected_current_world_ids": game_data.EXPECTED_CURRENT_WORLD_IDS,
            },
        }

    def _slot_location_data(self, name: str) -> dict[str, Any]:
        data = Locations.LOCATION_TABLE[name]
        return {
            "id": data.code,
            "category": data.category,
            "world_key": data.world_key,
            "challenge": data.challenge,
            "spark": data.spark,
            "chain": data.chain,
        }

    def _slot_challenge_data(self, challenge: game_data.ChallengeData) -> dict[str, Any]:
        return {
            "world_key": challenge.world_key,
            "world_name": challenge.world_name,
            "challenge": challenge.challenge,
            "type": challenge.challenge_type,
            "special": challenge.special,
            "spark_reward": challenge.spark_reward,
            "block_value": challenge.block_value,
            "logic_objects": list(game_data.challenge_logic_object_names(challenge)),
            "possible_requirements": [
                {
                    "objects": list(requirement.objects),
                    "max_spark": requirement.max_spark,
                }
                for requirement in game_data.possible_challenge_requirements(challenge)
            ],
            "objects": [
                {
                    "name": requirement.name,
                    "selected_value": requirement.selected_value,
                    "global_value": requirement.global_value,
                    "item": game_data.object_item_name(requirement.name),
                }
                for requirement in challenge.objects
            ],
        }

    def write_spoiler_header(self, spoiler_handle) -> None:
        spoiler_handle.write("\nCreate Settings:\n\n")
        spoiler_handle.write(f"Starting World: {game_data.WORLD_NAMES[self.starting_world_key]}\n")
        goal = "Spark Hunt (Goal World ignored)" if self.goal_world_key is None else game_data.WORLD_NAMES[self.goal_world_key]
        spoiler_handle.write(f"Goal: {goal}\n")

    def generate_output(self, output_directory: str) -> None:
        output = {
            "slot_data": self.fill_slot_data(),
            "location_to_item": {
                location.name: {
                    "item": location.item.name if location.item else None,
                    "player": location.item.player if location.item else None,
                }
                for location in self.multiworld.get_filled_locations(self.player)
                if location.address is not None
            },
        }
        filename = f"{self.multiworld.get_out_file_name_base(self.player)}.apcreate"
        with open(os.path.join(output_directory, filename), "w", encoding="utf-8") as output_file:
            json.dump(output, output_file, indent=2, sort_keys=True)
