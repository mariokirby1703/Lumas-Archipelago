from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from BaseClasses import Region
from worlds.AutoWorld import World

from . import Items, Locations, Regions, Rules, web_world
from .Addresses import addresses
from .Names import item_names, location_names, region_names
from .Options import Goal, IncludedDifficulties, MarbleBalanceOptions, HardModeUnlock
from .world_constants import (
    BONUS_WORLDS,
    DIFFICULTIES,
    GAME_NAME,
    HARD_BONUS_WORLD_DISPLAY_NAMES,
    MARBLES,
    NORMAL_WORLDS,
    WORLD_DISPLAY_NAMES,
    world_index_for,
)


class MarbleBalanceWorld(World):
    """
    Marble Saga Kororinpa / Marbles! Balance Challenge is a marble rolling puzzle game where AP controls
    world access, AP-side Green Gem and Stump Temple Piece counters, marbles, vehicles, and optional checks.
    """

    game = GAME_NAME
    web = web_world.MarbleBalanceWebWorld()
    options_dataclass = MarbleBalanceOptions
    options: MarbleBalanceOptions

    item_name_to_id = Items.ITEM_NAME_TO_ID
    location_name_to_id = Locations.LOCATION_NAME_TO_ID
    item_name_groups = Items.item_groups
    location_name_groups = Locations.location_name_groups

    item_type = Items.MarbleBalanceItem
    location_type = Locations.MarbleBalanceLocation

    topology_present = False
    ut_can_gen_without_yaml = True

    enabled_difficulties: tuple[str, ...]
    enabled_worlds_by_difficulty: dict[str, tuple[str, ...]]
    active_location_names: list[str]
    green_gem_location_count: int
    stump_piece_location_count: int
    starting_marble: str | None
    starting_worlds_by_difficulty: dict[str, str]
    uses_hard_mode_item: bool

    def generate_early(self) -> None:
        self._apply_ut_slot_data()
        self.starting_marble = getattr(self, "starting_marble", None) or self.random.choice(MARBLES)
        if self.options.included_difficulties == IncludedDifficulties.option_all:
            difficulties = list(DIFFICULTIES)
        elif self.options.included_difficulties == IncludedDifficulties.option_normal_and_hard:
            difficulties = ["Normal", "Hard"]
        elif self.options.included_difficulties == IncludedDifficulties.option_easy_and_normal:
            difficulties = ["Easy", "Normal"]
        else:
            difficulties = ["Normal"]

        if self.options.goal == Goal.option_stump_temple_level_10_hard and "Hard" not in difficulties:
            difficulties.append("Hard")

        self.enabled_difficulties = tuple(difficulties)
        self.enabled_worlds_by_difficulty = {difficulty: tuple(NORMAL_WORLDS) for difficulty in self.enabled_difficulties}
        self.starting_worlds_by_difficulty = getattr(
            self,
            "starting_worlds_by_difficulty",
            None,
        ) or self._choose_starting_worlds()
        self.uses_hard_mode_item = (
            "Hard" in self.enabled_difficulties
            and self.options.hard_mode_unlock == HardModeUnlock.option_item
        )

    @staticmethod
    def interpret_slot_data(slot_data: dict[str, Any]) -> dict[str, Any]:
        return slot_data

    def _apply_ut_slot_data(self) -> None:
        re_gen_passthrough = getattr(self.multiworld, "re_gen_passthrough", {})
        slot_data = re_gen_passthrough.get(self.game)
        if not slot_data:
            return

        for key, value in slot_data.get("options", {}).items():
            option = getattr(self.options, key, None)
            if option is not None:
                setattr(self.options, key, option.from_any(value))

        starting_worlds = slot_data.get("starting_worlds")
        if isinstance(starting_worlds, dict):
            self.starting_worlds_by_difficulty = dict(starting_worlds)

        starting_marble = slot_data.get("starting_marble")
        if isinstance(starting_marble, str):
            self.starting_marble = starting_marble

    def _choose_starting_worlds(self) -> dict[str, str]:
        if not self.options.random_starting_world:
            return {difficulty: "W1" for difficulty in self.enabled_difficulties}

        starting_worlds: dict[str, str] = {}
        for difficulty in self.enabled_difficulties:
            candidates = list(NORMAL_WORLDS)
            if difficulty == "Hard" or difficulty == "Normal" and "Easy" not in self.enabled_difficulties:
                candidates += list(BONUS_WORLDS)
            if difficulty == "Normal" and self.options.goal == Goal.option_stump_temple_level_10_normal:
                candidates.remove("W7")
            if difficulty == "Hard" and self.options.goal == Goal.option_stump_temple_level_10_hard:
                candidates.remove("W7")
            if difficulty != "Hard" and self.options.split_vehicle_world_access:
                candidates = [world for world in candidates if world not in {"W5", "W6"}]
            starting_worlds[difficulty] = self.random.choice(candidates)
        return starting_worlds

    def create_regions(self) -> None:
        Regions.create_and_connect_regions(self)
        Locations.create_locations(self)
        self._place_counter_items()
        self._place_victory_item()
        self.active_location_names = [location.name for location in self.get_locations()]
        self.green_gem_location_count = sum(
            1
            for name in self.active_location_names
            if name in Locations.LOCATION_TABLE and Locations.LOCATION_TABLE[name].category == "green_gem"
        )
        self.stump_piece_location_count = sum(
            1
            for name in self.active_location_names
            if name in Locations.LOCATION_TABLE and Locations.LOCATION_TABLE[name].category == "stump_piece"
        )

    def set_rules(self) -> None:
        Rules.set_all_rules(self)

    def create_items(self) -> None:
        self._push_starting_access_items()
        Items.create_all_items(self)

    def create_item(self, name: str) -> Items.MarbleBalanceItem:
        return Items.create_item(self, name)

    def _spoiler_world_name(self, difficulty: str, world: str) -> str:
        if difficulty == "Hard" and world in HARD_BONUS_WORLD_DISPLAY_NAMES:
            return HARD_BONUS_WORLD_DISPLAY_NAMES[world]
        return WORLD_DISPLAY_NAMES[world]

    def write_spoiler_header(self, spoiler_handle) -> None:
        spoiler_handle.write("\nStarting Worlds:\n\n")
        for difficulty in self.enabled_difficulties:
            world = self.starting_worlds_by_difficulty[difficulty]
            spoiler_handle.write(f"World {difficulty}: {self._spoiler_world_name(difficulty, world)}\n")

    def _place_victory_item(self) -> None:
        difficulty = "Hard" if self.options.goal == Goal.option_stump_temple_level_10_hard else "Normal"
        victory_location = self.get_location(location_names.goal_location_name(difficulty, "W7", 10))
        victory_location.place_locked_item(self.create_item(item_names.VICTORY))

    def _place_counter_items(self) -> None:
        difficulty = "Hard" if self.options.goal == Goal.option_stump_temple_level_10_hard else "Normal"
        w7_name = Locations.counter_stump_unlock_name(difficulty, self.options.required_stump_pieces_for_w7.value)
        self.get_location(w7_name).place_locked_item(self.create_item(item_names.world_access_name(difficulty, "W7")))

        if self.options.hard_mode_unlock == HardModeUnlock.option_green_gems:
            hard_name = Locations.counter_hard_mode_name(self.options.required_green_gems_for_hard.value)
            self.get_location(hard_name).place_locked_item(self.create_item(item_names.HARD_MODE))

    def _push_starting_access_items(self) -> None:
        pushed: set[str] = set()
        for difficulty, world in self.starting_worlds_by_difficulty.items():
            if world in NORMAL_WORLDS:
                item_name = item_names.world_access_name(difficulty, world)
                if item_name not in pushed:
                    self.push_precollected(self.create_item(item_name))
                    pushed.add(item_name)
            elif world in BONUS_WORLDS:
                item_name = item_names.world_access_name(difficulty, world)
                if item_name not in pushed:
                    self.push_precollected(self.create_item(item_name))
                    pushed.add(item_name)

    def get_filler_item_name(self) -> str:
        return Items.get_filler_item_name(self)

    def region_for_location_data(self, data: Locations.LocationData) -> Region:
        if data.category == "tutorial":
            return self.get_region(region_names.TUTORIALS)
        if data.category.startswith("counter_"):
            return self.get_region(region_names.MENU)
        if data.category == "balance_board":
            return self.get_region(region_names.WII_BALANCE_BOARD)
        if data.world in BONUS_WORLDS:
            assert data.difficulty is not None
            return self.get_region(region_names.world_region_name(data.difficulty, data.world))
        assert data.difficulty is not None and data.world is not None
        return self.get_region(region_names.world_region_name(data.difficulty, data.world))

    def fill_slot_data(self) -> Mapping[str, Any]:
        option_data = self.options.as_dict(
            "goal",
            "included_difficulties",
            "random_starting_world",
            "green_gem_sanity",
            "stump_piece_sanity",
            "required_stump_pieces_for_w7",
            "hard_mode_unlock",
            "required_green_gems_for_hard",
            "extra_counter_item_percentage",
            "tutorial_checks",
            "wii_balance_board_levels",
            "trap_chance",
            "blackout_trap_weight",
            "mirror_trap_weight",
            "inverse_trap_weight",
            "noclip_trap_weight",
            "split_vehicle_world_access",
            "anthony_sanity",
            "trophy_sanity",
        )

        active_location_data = {
            name: self._slot_location_data(name)
            for name in self.active_location_names
            if name in Locations.LOCATION_TABLE
        }

        return {
            "game": self.game,
            "seed_name": self.multiworld.seed_name,
            "player_name": self.multiworld.get_player_name(self.player),
            "enabled_difficulties": list(self.enabled_difficulties),
            "starting_worlds": self.starting_worlds_by_difficulty,
            "starting_marble": self.starting_marble,
            "options": option_data,
            "fixed_options": {
                "bonus_world_unlocks": True,
                "allow_free_mode_checks": False,
                "marble_randomization": True,
                "figure_roller_heads": True,
                "junk_items": "filler",
            },
            "locations": active_location_data,
            "static_addresses": addresses.STATIC_ADDRESSES,
            "marble_unlock_flags": addresses.MARBLE_UNLOCK_FLAGS,
            "figure_roller_head_unlock_flags": addresses.FIGURE_ROLLER_HEAD_UNLOCK_FLAGS,
            "junk_live_flags": addresses.JUNK_LIVE_FLAGS,
            "junk_saved_flags": addresses.JUNK_SAVED_FLAGS,
            "junk_unlock_flags": addresses.JUNK_UNLOCK_FLAGS,
            "vehicle_part_flags": addresses.VEHICLE_PART_FLAGS,
            "vehicle_flags": {
                "Easy": {
                    "Submarine": addresses.EASY_SUBMARINE_FLAG,
                    "Rocket Ship": addresses.EASY_ROCKET_SHIP_FLAG,
                },
                "Normal": {
                    "Submarine": addresses.NORMAL_SUBMARINE_FLAG,
                    "Rocket Ship": addresses.NORMAL_ROCKET_SHIP_FLAG,
                },
            },
            "safety": {
                "target_save_slot_index": 2,
                "world_map_stage_mode": 0x1D,
                "free_mode_stage_mode": 0x19,
                "tutorial_stage_mode": 0x1F,
                "balance_board_world_or_mode_index": 14,
                "stage_cleared_values": [94, 95],
            },
        }

    def _slot_location_data(self, name: str) -> dict[str, Any]:
        data = Locations.LOCATION_TABLE[name]
        output: dict[str, Any] = {
            "id": data.code,
            "category": data.category,
            "difficulty": data.difficulty,
            "world": data.world,
            "level": data.level,
        }
        if data.address:
            location_addresses = dict(data.address)
            if data.category == "green_gem":
                location_addresses["temporary_pickup"] = addresses.GREEN_OR_ANT_TEMPORARY_PICKUP
            if data.category == "stump_piece":
                location_addresses["temporary_pickup"] = (
                    addresses.JUNK_TEMPORARY_PICKUP
                    if data.difficulty == "Hard" or data.world in BONUS_WORLDS
                    else addresses.STUMP_TEMPORARY_PICKUP
                )
            if data.category == "ant":
                location_addresses["temporary_pickup"] = addresses.ANTHONY_TEMPORARY_PICKUP
            output["addresses"] = location_addresses
        if data.difficulty and data.world and data.level:
            output["stage_id"] = addresses.stage_id(data.difficulty, data.world, data.level)
            output["world_index"] = world_index_for(data.difficulty, data.world)
            output["stage_index"] = data.level - 1
        return output

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
        filename = f"{self.multiworld.get_out_file_name_base(self.player)}.apmbc"
        with open(os.path.join(output_directory, filename), "w", encoding="utf-8") as output_file:
            json.dump(output, output_file, indent=2, sort_keys=True)
