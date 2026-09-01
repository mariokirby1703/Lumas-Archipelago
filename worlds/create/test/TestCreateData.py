from BaseClasses import ItemClassification, LocationProgressType

from . import CreateTestBase
from .. import Rules, game_data
from ..Locations import LOCATION_TABLE
from ..Options import GoalWorld, StartingWorld
from ..world_constants import II_WORLDS, ITEM_VICTORY, SPARK_ITEM_AMOUNTS


class TestCreateData(CreateTestBase):
    def test_data_counts(self) -> None:
        self.assertEqual(tuple(range(262)), tuple(obj.value for obj in game_data.GLOBAL_OBJECT_DATA))
        self.assertEqual(194, len(game_data.UNLOCKABLE_OBJECTS))
        self.assertEqual(68, len([obj for obj in game_data.GLOBAL_OBJECT_DATA if not obj.unlockable]))
        self.assertEqual(140, len(game_data.ALL_CHALLENGES))
        self.assertEqual(141, len((game_data.HUB_CHALLENGE_DATA, *game_data.ALL_CHALLENGES)))
        self.assertEqual(
            539,
            game_data.HUB_CHALLENGE_DATA.spark_reward
            + sum(challenge.spark_reward for challenge in game_data.ALL_CHALLENGES),
        )
        local_challenges = [
            challenge for challenge in (game_data.HUB_CHALLENGE_DATA, *game_data.ALL_CHALLENGES)
            if challenge.challenge_type == "local"
        ]
        global_specials = [
            challenge for challenge in (game_data.HUB_CHALLENGE_DATA, *game_data.ALL_CHALLENGES)
            if challenge.challenge_type == "global"
        ]
        contraption_challenges = [
            challenge for challenge in global_specials
            if challenge.special == "Contraption-o-matic"
        ]
        scoretacular_challenges = [
            challenge for challenge in global_specials
            if challenge.special == "Scoretacular"
        ]
        self.assertEqual(79, len(local_challenges))
        self.assertEqual(62, len(global_specials))
        self.assertEqual(39, len(contraption_challenges))
        self.assertEqual(23, len(scoretacular_challenges))

    def test_location_counts(self) -> None:
        spark_locations = [data for data in LOCATION_TABLE.values() if data.category == "spark"]
        challenge_locations = [data for data in LOCATION_TABLE.values() if data.category == "challenge"]
        chain_locations = [data for data in LOCATION_TABLE.values() if data.category == "create_chain"]

        self.assertEqual(539, len(spark_locations))
        self.assertEqual(141, len(challenge_locations))
        self.assertEqual(71, len(chain_locations))

    def test_corrected_requirements(self) -> None:
        future_world_9 = game_data.CHALLENGE_TABLE[("W07", 9)]
        outer_space_ii_10 = game_data.CHALLENGE_TABLE[("W13", 10)]

        self.assertIn("Jumbo Ramp", {requirement.name for requirement in future_world_9.objects})
        self.assertNotIn("Jumbo Bot", {requirement.name for requirement in future_world_9.objects})
        self.assertIn("Laser Cannon", {requirement.name for requirement in outer_space_ii_10.objects})

    def test_yaml_defaults_are_compact_random(self) -> None:
        self.assertEqual("random", StartingWorld.default)
        self.assertEqual("random", GoalWorld.default)

    def test_ii_world_options_display_uppercase_ii(self) -> None:
        self.assertEqual("Theme Park II", StartingWorld.get_option_name(11))
        self.assertEqual("Future World II", GoalWorld.get_option_name(14))

    def test_item_names_are_plain_object_names(self) -> None:
        self.assertEqual("Jumbo Ramp", game_data.object_item_name("Jumbo Ramp"))
        self.assertNotIn("Jumbo Bot", game_data.UNLOCKABLE_OBJECTS_BY_NAME)
        self.assertNotIn("Scoretacular", game_data.UNLOCKABLE_OBJECTS_BY_NAME)
        self.assertNotIn("Contraption-o-matic", game_data.UNLOCKABLE_OBJECTS_BY_NAME)

    def test_contraption_o_matic_requires_structure_objects(self) -> None:
        expected_values = {37, 38, 39, 40, 41}
        for challenge in game_data.ALL_CHALLENGES:
            if challenge.special == "Contraption-o-matic":
                with self.subTest(world=challenge.world_key, challenge=challenge.challenge):
                    self.assertEqual(expected_values, {requirement.global_value for requirement in challenge.objects})

    def test_local_block_values_are_outside_local_index_range(self) -> None:
        for challenge in (game_data.HUB_CHALLENGE_DATA, *game_data.ALL_CHALLENGES):
            if challenge.challenge_type == "local":
                expected_block = len(challenge.objects) + 1
                self.assertEqual(expected_block, challenge.block_value)
                selected_values = sorted(requirement.selected_value for requirement in challenge.objects)
                self.assertEqual(list(range(len(challenge.objects))), selected_values)
                for requirement in challenge.objects:
                    self.assertIn(requirement.global_value, game_data.UNLOCKABLE_OBJECT_VALUES)

    def test_out_of_logic_possible_object_names_are_valid(self) -> None:
        self.assertEqual(
            set(),
            game_data.POSSIBLE_CHALLENGE_OBJECT_NAMES - set(game_data.UNLOCKABLE_OBJECTS_BY_NAME),
        )

    def test_scoretacular_uses_bouncer_as_logic_requirement(self) -> None:
        for challenge in game_data.ALL_CHALLENGES:
            if challenge.special == "Scoretacular":
                with self.subTest(world=challenge.world_key, challenge=challenge.challenge):
                    self.assertEqual(("Bouncer",), game_data.challenge_logic_object_names(challenge))

    def test_slot_data_includes_logic_and_possible_requirements(self) -> None:
        slot_challenge = self.world.fill_slot_data()["challenges"]["W01:7"]

        self.assertEqual(["Bouncer"], slot_challenge["logic_objects"])
        self.assertIn(
            {"objects": ["Jumbo Ramp"], "max_spark": 3},
            slot_challenge["possible_requirements"],
        )

    def test_spark_amounts_keep_vanilla_variety(self) -> None:
        amount_counts = {
            amount: game_data.spark_item_amounts_for_total(516).count(amount)
            for amount in (1, 2, 3, 6)
        }

        self.assertEqual(516, sum(amount * count for amount, count in amount_counts.items()))
        for amount in (1, 2, 3, 6):
            self.assertGreater(amount_counts[amount], 0)


class TestCreateCompactMode(CreateTestBase):
    options = {
        "create_chain_checks": True,
    }

    def test_uses_spark_locations(self) -> None:
        location_names = {location.name for location in self.multiworld.get_locations()}
        self.assertIn("Hub World Challenge 1 - Reward", location_names)
        self.assertIn("Theme Park Challenge 01 Spark 1", location_names)
        self.assertNotIn("Theme Park Challenge 01", location_names)

    def test_ii_worlds_are_disabled_by_default(self) -> None:
        location_names = {location.name for location in self.multiworld.get_locations()}
        item_names = {item.name for item in self.multiworld.itempool}
        for world_key in II_WORLDS:
            world_name = game_data.WORLD_NAMES[world_key]
            self.assertFalse(any(name.startswith(world_name) for name in location_names))
        self.assertNotIn(game_data.world_access_item_name(world_key), item_names)

    def test_all_unlockable_objects_are_in_the_item_pool(self) -> None:
        object_items = [
            item for item in self.multiworld.itempool
            if item.name in game_data.UNLOCKABLE_OBJECTS_BY_NAME
        ]
        reserved_object_items = [
            location.item for location in self.multiworld.get_locations(self.player)
            if location.item and location.item.name in game_data.UNLOCKABLE_OBJECTS_BY_NAME
        ]
        object_names = {item.name for item in (*object_items, *reserved_object_items)}
        self.assertEqual(
            {game_data.object_item_name(obj.name) for obj in game_data.UNLOCKABLE_OBJECTS},
            object_names,
        )
        soccer_ball = next(
            obj for obj in game_data.UNLOCKABLE_OBJECTS
            if obj.name == "Soccer Ball"
        )
        soccer_ball_item = next(item for item in object_items if item.name == game_data.object_item_name(soccer_ball.name))
        self.assertEqual(ItemClassification.useful, soccer_ball_item.classification)


class TestCreateWithIIWorlds(CreateTestBase):
    options = {
        "include_ii_worlds": True,
    }

    def test_ii_worlds_can_be_included(self) -> None:
        location_names = {location.name for location in self.multiworld.get_locations()}
        self.assertIn("Future World II Challenge 10 Spark 1", location_names)


class TestCreateSelectedIIStartWithoutFullIIPool(CreateTestBase):
    options = {
        "starting_world": "future_world_ii",
        "goal_world": "theme_park",
        "include_ii_worlds": False,
    }

    def test_selected_ii_start_is_kept(self) -> None:
        self.assertEqual("W14", self.world.starting_world_key)
        self.assertIn("W14", self.world.active_world_keys)
        self.assertTrue(self.can_reach_location("Future World II Create Chain 1"))
        self.assertFalse(self.multiworld.early_items[self.player])
        self.assertFalse(self.multiworld.local_early_items[self.player])


class TestCreateOuterSpaceIIStartBootstrap(CreateTestBase):
    options = {
        "starting_world": "outer_space_ii",
        "goal_world": "theme_park",
        "include_ii_worlds": False,
    }

    def test_possible_requirement_bootstraps_object_heavy_start(self) -> None:
        self.assertEqual("W13", self.world.starting_world_key)
        self.assertEqual(["Dark Matter"], self.world._starting_challenge_object_names("W13"))
        self.multiworld.state.collect(self.world.create_item("Dark Matter"))
        self.assertTrue(self.can_reach_location("Outer Space II Challenge 01 Spark 1"))


class TestCreateProgressiveLogic(CreateTestBase):
    options = {
        "starting_world": "theme_park",
        "goal_world": "future_world_ii",
        "create_chain_checks": True,
    }

    def test_create_chains_remain_normal_reachable_checks(self) -> None:
        self.assertTrue(self.can_reach_location("Hub World Create Chain"))
        self.assertIsNone(self.multiworld.get_location("Hub World Create Chain", self.player).item)
        self.assertTrue(self.can_reach_location("Theme Park Create Chain 1"))
        self.assertFalse(self.can_reach_location("Theme Park Create Chain 2"))
        required_items = {
            game_data.object_item_name(requirement.name)
            for challenge in range(1, 3)
            for requirement in game_data.CHALLENGE_TABLE[("W01", challenge)].objects
            if requirement.global_value in game_data.UNLOCKABLE_OBJECT_VALUES
        }
        self.collect_by_name(required_items)
        self.assertTrue(self.can_reach_location("Theme Park Create Chain 2"))
        self.assertFalse(self.can_reach_location("Theme Park Create Chain 3"))
        self.assertEqual(
            LocationProgressType.DEFAULT,
            self.multiworld.get_location("Theme Park Create Chain 5", self.player).progress_type,
        )

    def test_starting_world_is_ap_logic_accessible_without_chain_item(self) -> None:
        required_items = {
            game_data.object_item_name(requirement.name)
            for requirement in game_data.CHALLENGE_TABLE[("W01", 1)].objects
            if requirement.global_value in game_data.UNLOCKABLE_OBJECT_VALUES
        }
        for item_name in required_items:
            self.multiworld.state.collect(self.world.create_item(item_name))
        self.assertTrue(self.can_reach_location("Theme Park Challenge 01 Spark 1"))


class TestCreateChallengeLogic(CreateTestBase):
    options = {
        "starting_world": "theme_park",
        "goal_world": "future_world_ii",
        "create_chain_checks": True,
    }

    def test_challenge_four_can_follow_any_starting_challenge(self) -> None:
        required_items = {
            game_data.object_item_name(requirement.name)
            for challenge in range(1, 5)
            for requirement in game_data.CHALLENGE_TABLE[("W01", challenge)].objects
            if requirement.global_value in game_data.UNLOCKABLE_OBJECT_VALUES
        }
        self.collect_by_name(required_items)

        self.assertTrue(self.can_reach_location("Theme Park Challenge 01 Spark 1"))
        self.assertTrue(self.can_reach_location("Theme Park Challenge 02 Spark 1"))
        self.assertTrue(self.can_reach_location("Theme Park Challenge 03 Spark 1"))
        self.assertTrue(self.can_reach_location("Theme Park Challenge 04 Spark 1"))

    def test_scoretacular_requires_bouncer_for_strict_logic(self) -> None:
        required_items = {
            game_data.object_item_name(requirement.name)
            for challenge in range(1, 5)
            for requirement in game_data.CHALLENGE_TABLE[("W01", challenge)].objects
            if requirement.global_value in game_data.UNLOCKABLE_OBJECT_VALUES
        }
        self.collect_by_name(required_items)

        self.assertFalse(self.can_reach_location("Theme Park Challenge 07 Spark 1"))
        self.collect_by_name({"Bouncer"})
        self.assertTrue(self.can_reach_location("Theme Park Challenge 07 Spark 1"))

    def test_out_of_logic_possible_rule_marks_limited_sparks(self) -> None:
        required_items = {
            game_data.object_item_name(requirement.name)
            for challenge in range(1, 5)
            for requirement in game_data.CHALLENGE_TABLE[("W01", challenge)].objects
            if requirement.global_value in game_data.UNLOCKABLE_OBJECT_VALUES
        }
        self.collect_by_name(required_items | {"Jumbo Ramp"})
        spark_3 = self.multiworld.get_location("Theme Park Challenge 07 Spark 3", self.player)
        spark_4 = self.multiworld.get_location("Theme Park Challenge 07 Spark 4", self.player)

        self.assertTrue(spark_3.out_of_logic_possible)
        self.assertTrue(spark_3.possible_access_rule(self.multiworld.state))
        self.assertFalse(hasattr(spark_4, "possible_access_rule") and spark_4.possible_access_rule(self.multiworld.state))

    def test_out_of_logic_possible_rule_supports_contraption_combos(self) -> None:
        required_items = {
            game_data.object_item_name(requirement.name)
            for challenge in range(1, 6)
            for requirement in game_data.CHALLENGE_TABLE[("W01", challenge)].objects
            if requirement.global_value in game_data.UNLOCKABLE_OBJECT_VALUES
        }
        self.collect_by_name(required_items)
        location = self.multiworld.get_location("Theme Park Challenge 08 Spark 1", self.player)

        self.assertTrue(location.out_of_logic_possible)
        self.assertFalse(self.can_reach_location("Theme Park Challenge 08 Spark 1"))
        self.assertFalse(location.possible_access_rule(self.multiworld.state))

        self.collect_by_name({"Girder"})
        self.assertTrue(location.possible_access_rule(self.multiworld.state))

    def test_universal_tracker_can_use_possible_rule_without_changing_normal_logic(self) -> None:
        required_items = {
            game_data.object_item_name(requirement.name)
            for challenge in range(1, 5)
            for requirement in game_data.CHALLENGE_TABLE[("W01", challenge)].objects
            if requirement.global_value in game_data.UNLOCKABLE_OBJECT_VALUES
        }
        self.collect_by_name(required_items | {"Jumbo Ramp"})
        location = self.multiworld.get_location("Theme Park Challenge 07 Spark 3", self.player)

        self.assertFalse(self.can_reach_location("Theme Park Challenge 07 Spark 3"))
        self.assertTrue(location.possible_access_rule(self.multiworld.state))

        self.multiworld.generation_is_fake = True
        Rules.set_location_rules(self.world)
        self.assertEqual(LocationProgressType.PRIORITY, location.progress_type)
        self.assertTrue(self.can_reach_location("Theme Park Challenge 07 Spark 3"))


class TestCreateRequiredSparks(CreateTestBase):
    options = {
        "starting_world": "theme_park",
        "goal_world": "future_world_ii",
        "create_chain_checks": True,
        "required_sparks": 610,
    }

    def test_required_sparks_force_per_spark_locations_and_exact_total(self) -> None:
        location_names = {location.name for location in self.multiworld.get_locations()}
        self.assertIn("Theme Park Challenge 01 Spark 1", location_names)
        self.assertNotIn("Theme Park Challenge 01", location_names)

        spark_total = sum(
            SPARK_ITEM_AMOUNTS.get(item.name, 0)
            for item in self.multiworld.itempool
        )
        self.assertEqual(610, spark_total)

    def test_required_sparks_are_part_of_completion_logic(self) -> None:
        state = self.multiworld.state
        state.collect(self.world.create_item(ITEM_VICTORY))
        self.assertFalse(self.multiworld.can_beat_game(state))
        for item_name, amount in SPARK_ITEM_AMOUNTS.items():
            for _ in range(610 // amount + 1):
                if sum(state.count(name, self.player) * value for name, value in SPARK_ITEM_AMOUNTS.items()) >= 610:
                    break
                state.collect(self.world.create_item(item_name))
        self.assertTrue(self.multiworld.can_beat_game(state))


class TestCreateChainsDisabled(CreateTestBase):
    options = {
        "starting_world": "theme_park",
        "goal_world": "future_world",
        "create_chain_checks": False,
        "include_ii_worlds": False,
        "required_sparks": 516,
    }

    def test_hub_chain_stays_enabled_with_locked_jumbo_ramp(self) -> None:
        location_names = {location.name for location in self.multiworld.get_locations()}
        self.assertIn("Hub World Create Chain", location_names)
        self.assertIn("Hub World Challenge 1 - Reward", location_names)
        self.assertNotIn("Theme Park Create Chain 1", location_names)
        hub_chain = self.multiworld.get_location("Hub World Create Chain", self.player)
        self.assertEqual("Jumbo Ramp", hub_chain.item.name)

    def test_516_sparks_fit_with_capped_extra_sparks_when_chains_and_ii_are_disabled(self) -> None:
        spark_total = sum(
            SPARK_ITEM_AMOUNTS.get(item.name, 0)
            for item in self.multiworld.itempool
        )
        extra_spark_total = spark_total - self.world.required_sparks
        filler_count = sum(1 for item in self.multiworld.itempool if item.name == "Creativity")
        self.assertEqual(516, self.world.required_sparks)
        self.assertGreaterEqual(spark_total, 516)
        self.assertLessEqual(extra_spark_total, int(516 * 0.3))
        self.assertGreater(filler_count, 0)


class TestCreateSparkHunt(CreateTestBase):
    options = {
        "starting_world": "theme_park",
        "goal_world": "future_world",
        "create_chain_checks": True,
        "include_ii_worlds": False,
        "required_sparks": 610,
        "spark_goal_mode": "spark_hunt",
    }

    def test_spark_hunt_completion_uses_ap_spark_counter_only(self) -> None:
        self.assertFalse(any(location.item and location.item.name == ITEM_VICTORY for location in self.multiworld.get_locations()))
        state = self.multiworld.state
        self.assertFalse(self.multiworld.can_beat_game(state))
        for item_name, amount in SPARK_ITEM_AMOUNTS.items():
            for _ in range(610 // amount + 1):
                if sum(state.count(name, self.player) * value for name, value in SPARK_ITEM_AMOUNTS.items()) >= 610:
                    break
                state.collect(self.world.create_item(item_name))
        self.assertTrue(self.multiworld.can_beat_game(state))


class TestCreateSparkGoalWorldUnlock(CreateTestBase):
    options = {
        "starting_world": "theme_park",
        "goal_world": "future_world",
        "create_chain_checks": True,
        "include_ii_worlds": False,
        "required_sparks": 610,
        "spark_goal_mode": "goal_world_unlock",
    }

    def test_required_sparks_unlock_goal_world_logic(self) -> None:
        state = self.multiworld.state
        entrance = self.multiworld.get_entrance("Hub to Future World", self.player)
        self.assertFalse(entrance.can_reach(state))
        for item_name, amount in SPARK_ITEM_AMOUNTS.items():
            for _ in range(610 // amount + 1):
                if sum(state.count(name, self.player) * value for name, value in SPARK_ITEM_AMOUNTS.items()) >= 610:
                    break
                state.collect(self.world.create_item(item_name))
        self.assertTrue(entrance.can_reach(state))
