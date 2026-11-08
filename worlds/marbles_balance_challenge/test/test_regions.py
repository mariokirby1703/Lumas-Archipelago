from test.bases import WorldTestBase
from ..Addresses.regions import NTSC_U, PAL, translate_address
from ..Names import location_names


class TestPAL(WorldTestBase):
    game = "Marbles! Balance Challenge"
    options = {"wii_balance_board_levels": True}

    def test_pal_profile(self):
        data = self.world.fill_slot_data()
        self.assertEqual(data["disc_game_id"], "RK6P18")
        self.assertEqual(sum(x["category"] == "balance_board" for x in data["locations"].values()), 100)
        self.assertEqual(data["static_addresses"]["current_world_or_mode_index"], 0x8049D945)
        self.assertEqual(data["marble_unlock_flags"]["Marble"], 0x804DF36E)


class TestNTSCU(WorldTestBase):
    game = "Marbles! Balance Challenge"
    options = {"game_region": "ntsc_u", "wii_balance_board_levels": True,
               "included_difficulties": "all", "trophy_sanity": "all", "anthony_sanity": True}

    def test_us_profile(self):
        data = self.world.fill_slot_data()
        self.assertEqual(data["disc_game_id"], "RK6E18")
        self.assertEqual(data["disc_title"], "Marble Saga: Kororinpa")
        boards = [x["level"] for x in data["locations"].values() if x["category"] == "balance_board"]
        self.assertEqual(boards, list(range(1, 31)))
        self.assertEqual(data["static_addresses"]["current_world_or_mode_index"], 0x80498745)
        self.assertEqual(data["static_addresses"]["green_or_ant_temporary_pickup"], 0x804D318F)
        self.assertEqual(data["marble_unlock_flags"]["Marble"], 0x804D1446)
        first = data["locations"][location_names.goal_location_name("Easy", "W1", 1)]
        self.assertEqual(first["addresses"]["trophy"], 0x804BF770)
        self.assertEqual(first["addresses"]["state"], 0x804BF764)
        self.assertTrue(all(value is None for value in data["junk_saved_flags"].values()))
        self.assertIsNone(data["static_addresses"]["noclip_trap_flag"])
        self.assertFalse(data["safety"]["experimental_traps_supported"])
        self.assertFalse(any(item.name.endswith("Trap") for item in self.multiworld.itempool))

    def test_profiles_are_not_mutated_across_serialization(self):
        self.assertEqual(self.world.fill_slot_data(), self.world.fill_slot_data())
        self.assertEqual(translate_address(0x804CA790, PAL), 0x804CA790)
        self.assertEqual(translate_address(0x804CA790, NTSC_U), 0x804BF770)

    def test_disc_and_goal_detection(self):
        from unittest.mock import patch
        from ..client import client
        data = self.world.fill_slot_data()
        self.assertTrue(client.disc_matches_slot(b"RK6E18", data))
        self.assertFalse(client.disc_matches_slot(b"RK6P18", data))
        self.assertTrue(client.disc_matches_slot(b"RK6P18", {}))
        self.assertFalse(client.disc_matches_slot(b"RK6J18", {}))
        with patch.object(client, "read_u8", return_value=94) as read:
            self.assertEqual(client.goal_active_count(data), client.GOAL_ENTER_THRESHOLD)
            read.assert_called_once_with(0x80487FB5)
        with patch.object(client, "read_u8", return_value=0):
            self.assertEqual(client.goal_active_count(data), 0)


    def test_save_slot_guard_prevents_ram_writes(self):
        import asyncio
        from types import SimpleNamespace
        from unittest.mock import patch
        from ..client import client
        ctx = SimpleNamespace(slot_data=self.world.fill_slot_data(), save_slot_ready=False,
                              _save_slot_logged=False)
        with patch.object(client, "read_u8", return_value=0), \
                patch.object(client, "apply_starting_access") as write:
            asyncio.run(client.sync_game_state(ctx))
            write.assert_not_called()
            self.assertFalse(ctx.save_slot_ready)

    def test_bonus_mirror_trophies(self):
        from ..Addresses import addresses
        for difficulty in ("Normal", "Hard"):
            for world in ("WA", "WB", "WC"):
                record = addresses.bonus_level_record(difficulty, world, 1)
                self.assertEqual(record["mirror_trophy"], record["trophy"] + 0x50)
