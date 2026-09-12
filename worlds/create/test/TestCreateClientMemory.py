from __future__ import annotations

import sys
import struct
import types
import unittest
from collections import deque
from types import SimpleNamespace
from unittest.mock import Mock, patch

from .. import game_data
from ..client import client
from ..client import popup_runtime as popup


class FakeDolphinMemoryEngine:
    def __init__(self) -> None:
        self.bytes: dict[int, int] = {}

    def read_byte(self, address: int) -> int:
        return self.bytes.get(address, 0)

    def write_byte(self, address: int, value: int) -> None:
        self.bytes[address] = value & 0xFF

    def read_bytes(self, address: int, length: int) -> bytes:
        return bytes(self.bytes.get(address + offset, 0) for offset in range(length))

    def write_bytes(self, address: int, data: bytes) -> None:
        for offset, value in enumerate(data):
            self.bytes[address + offset] = value

    def write_u32(self, address: int, value: int) -> None:
        self.write_bytes(address, value.to_bytes(4, "big"))

    def read_u32(self, address: int) -> int:
        return int.from_bytes(self.read_bytes(address, 4), "big")


def install_fake_dolphin() -> FakeDolphinMemoryEngine:
    fake = FakeDolphinMemoryEngine()
    module = types.SimpleNamespace(
        read_byte=fake.read_byte,
        write_byte=fake.write_byte,
        read_bytes=fake.read_bytes,
        write_bytes=fake.write_bytes,
    )
    sys.modules["dolphin_memory_engine"] = module
    return fake


def make_context() -> SimpleNamespace:
    return SimpleNamespace(
        slot_data={
            "ram": {
                "addresses": game_data.RAM_ADDRESSES,
                "object_system": game_data.RAM_MAP["object_system"],
                "challenge_records": game_data.CHALLENGE_RECORDS,
                "ii_world_flags": game_data.II_WORLD_FLAGS_BY_NAME,
                "confirmed_current_world_ids": game_data.CONFIRMED_CURRENT_WORLD_IDS,
                "expected_current_world_ids": game_data.EXPECTED_CURRENT_WORLD_IDS,
            },
            "objects": {
                game_data.object_item_name(obj.name): {
                    "name": obj.name,
                    "global_value": obj.value,
                }
                for obj in game_data.UNLOCKABLE_OBJECTS
            },
            "challenges": {
                f"{challenge.world_key}:{challenge.challenge}": {
                    "world_key": challenge.world_key,
                    "world_name": challenge.world_name,
                    "challenge": challenge.challenge,
                    "type": challenge.challenge_type,
                    "special": challenge.special,
                    "spark_reward": challenge.spark_reward,
                    "block_value": challenge.block_value,
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
                for challenge in (game_data.HUB_CHALLENGE_DATA, *game_data.ALL_CHALLENGES)
            },
            "worlds": {
                world_key: {
                    "name": game_data.WORLD_NAMES[world_key],
                    "access_item": game_data.world_access_item_name(world_key),
                    "hub_index": index,
                    "included": True,
                }
                for index, world_key in enumerate(game_data.WORLD_KEYS)
            },
            "starting_world": "W01",
            "goal_world": "W07",
            "locations": {},
            "required_sparks": 516,
            "spark_goal_mode": "goal_world_unlock",
            "options": {"create_chain_checks": True, "spark_goal_mode": "goal_world_unlock"},
        },
        save_slot_armed=True,
        checked_locations=set(),
        locations_checked=set(),
        items_received=[],
        _object_records={},
        _object_resync_pending=True,
        _object_resync_blocked_until=0.0,
        _last_received_object_values=frozenset(),
        _last_object_resync_at=0.0,
        _object_resolver_failure_logged=False,
        _object_resolver_retry_at=0.0,
        _object_resolver_trace={},
        _object_mem2_rehook_requested=False,
        _object_mem2_rehook_attempts=0,
        _challenge_palette_context=None,
        _challenge_palette_keys={},
        _challenge_palette_failure_logged=False,
        _contraption_patch_checked=False,
        _contraption_patch_applied=False,
        _chain_events_seen=set(),
        _chain_event_armed_contexts=set(),
        _chain_completion_context=None,
        _previous_chain_completion=None,
        _hub_chain_reward_pulses=0,
        _hub_chain_part_sequence=None,
        _chain_context_ready_at=0.0,
        _hub_event_ready_at=0.0,
        _hub_challenge_spark_armed=False,
        _previous_hub_challenge_sparks=None,
    )


def seed_object_registry(fake: FakeDolphinMemoryEngine, ctx: SimpleNamespace) -> dict[int, int]:
    object_system = ctx.slot_data["ram"]["object_system"]
    registry_root = int(object_system["registry_root"], 0)
    registry_key = int(object_system["registry_key"], 0)
    registry_entry = 0x80638000
    first_node = 0x91100000
    node_stride = 0x20
    records: dict[int, int] = {}

    fake.write_u32(registry_root, registry_entry)
    fake.write_u32(registry_entry + 0x0C, registry_key)
    fake.write_u32(registry_entry + 0x2C, first_node)

    for object_id in range(client.OBJECT_RECORD_COUNT):
        node = first_node + object_id * node_stride
        record = 0x91200000 + object_id * 0x40
        records[object_id] = record
        fake.write_u32(node + 0x10, record)
        fake.write_u32(node + 0x14, node + node_stride if object_id < client.OBJECT_RECORD_COUNT - 1 else 0)
    return records


class TestCreateClientObjectMemory(unittest.TestCase):
    def setUp(self) -> None:
        self.fake = install_fake_dolphin()
        self.ctx = make_context()
        self.records = seed_object_registry(self.fake, self.ctx)

    def test_mem2_read_failure_selects_verified_fallback_and_routes_writes(self) -> None:
        fallback = Mock()
        fallback.read.return_value = b"\x91\x15\xb4\x00"
        engine = sys.modules["dolphin_memory_engine"]
        client.reset_mem2_fallback()
        try:
            with patch.object(engine, "read_bytes", side_effect=RuntimeError("MEM2 missing")):
                with patch.object(client.sys, "platform", "win32"):
                    with patch("worlds.create.client.windows_mem2.WindowsMEM2", return_value=fallback):
                        self.assertEqual(0x9115B400, client.read_u32_be(0x9115B37C))
            client.write_u32_be(0x9115B37C, 123)
            fallback.write.assert_called_once_with(0x9115B37C, (123).to_bytes(4, "big"))
            client.write_u32_be(0x8068CD88, 100)
            self.assertEqual(100, self.fake.read_u32(0x8068CD88))
        finally:
            client.reset_mem2_fallback()
        fallback.close.assert_called_once()

    def test_mem1_read_failure_does_not_use_mem2_fallback(self) -> None:
        engine = sys.modules["dolphin_memory_engine"]
        with patch.object(engine, "read_bytes", side_effect=RuntimeError("MEM1 missing")):
            with patch("worlds.create.client.windows_mem2.WindowsMEM2") as fallback:
                with self.assertRaises(RuntimeError):
                    client.read_u32_be(0x80000000)
                fallback.assert_not_called()

    def test_mem2_mapping_rejects_private_and_guarded_regions(self) -> None:
        from ..client.windows_mem2 import MemoryRegion, mapped_ram
        region = MemoryRegion()
        region.size, region.state, region.kind, region.protect = 0x4000000, 0x1000, 0x40000, 4
        self.assertTrue(mapped_ram(region, 0x4000000))
        region.kind = 0x20000
        self.assertFalse(mapped_ram(region, 0x4000000))
        region.kind, region.protect = 0x40000, 0x104
        self.assertFalse(mapped_ram(region, 0x4000000))

    def test_mem2_mapping_bounds(self) -> None:
        from ..client.windows_mem2 import WindowsMEM2
        memory = WindowsMEM2.__new__(WindowsMEM2)
        memory.handle, memory.base = 1, 0x100000000
        self.assertEqual(0x10115B37C, memory._address(0x9115B37C, 4))
        for address, size in ((0x8FFFFFFF, 4), (0x93FFFFFF, 4), (0x94000000, 1)):
            with self.subTest(address=address), self.assertRaises(ValueError):
                memory._address(address, size)

    def test_unreadable_palette_candidate_does_not_abort_other_candidates(self) -> None:
        with patch.object(client, "read_u32_be", side_effect=[0x80640000, 0x912F0000]):
            with patch.object(client, "_read_challenge_object_list_candidate",
                              side_effect=[RuntimeError("unreadable candidate"), (0x912F1000, 1)]):
                self.assertEqual((0x912F1000, 1), client.resolve_current_challenge_object_list(1, self.ctx))

    def test_palette_memory_failure_does_not_escape_into_reconnect_loop(self) -> None:
        with patch.object(client, "_filter_current_challenge_palette", side_effect=RuntimeError("MEM2 missing")):
            self.assertFalse(client.filter_current_challenge_palette(self.ctx, True))
            self.assertTrue(self.ctx._challenge_palette_failure_logged)

    def test_object_registry_resolves_all_ids(self) -> None:
        records = client.resolve_object_records(self.ctx)

        self.assertEqual(client.OBJECT_RECORD_COUNT, len(records))
        self.assertEqual(self.records[13], records[13])
        self.assertEqual(self.records[126], records[126])

    def test_object_registry_rejects_non_u32_pointer(self) -> None:
        with patch.object(client, "read_u32_be", return_value=0x100000000):
            with self.assertRaisesRegex(RuntimeError, "unsigned 32-bit"):
                client.find_first_object_node(self.ctx)

    def test_object_registry_uses_matching_entry_object_node_pointer(self) -> None:
        object_system = self.ctx.slot_data["ram"]["object_system"]
        registry_root = int(object_system["registry_root"], 0)
        entry = self.fake.read_u32(registry_root)
        first_node = self.fake.read_u32(entry + 0x2C)

        self.assertEqual(first_node, client.find_first_object_node(self.ctx))

    def test_object_registry_retries_and_reports_recovery(self) -> None:
        now = [10.0]
        with (
            patch.object(client, "resolve_object_records", side_effect=[RuntimeError("heap rebuilding"), self.records]),
            patch.object(client.time, "monotonic", side_effect=lambda: now[0]),
            self.assertLogs(level="INFO") as logs,
        ):
            self.assertIsNone(client.object_records(self.ctx))
            now[0] = 10.5
            self.assertIsNone(client.object_records(self.ctx))
            now[0] = 11.1
            self.assertEqual(self.records, client.object_records(self.ctx))

        self.assertTrue(any("retry automatically" in line for line in logs.output))
        self.assertTrue(any("sync resumed" in line for line in logs.output))

    def test_mem2_read_failure_requests_dolphin_rehook(self) -> None:
        error = client.ObjectMemoryReadError(0x9115B37C, "Object 0 Availability Record pointer", RuntimeError())
        with patch.object(client, "resolve_object_records", side_effect=error):
            self.assertIsNone(client.object_records(self.ctx))

        self.assertTrue(self.ctx._object_mem2_rehook_requested)

    def test_object_sync_discards_records_that_change_during_write(self) -> None:
        self.ctx._object_records = self.records.copy()
        with (
            patch.object(client, "received_object_values", return_value={6}),
            patch.object(client, "apply_unowned_object_record", side_effect=RuntimeError("stale record")),
        ):
            client.sync_object_availability(self.ctx, challenge_active=False)

        self.assertEqual({}, self.ctx._object_records)
        self.assertTrue(self.ctx._object_resync_pending)
        self.assertGreater(self.ctx._object_resolver_retry_at, 0.0)

    def test_object_resync_writes_owned_and_unowned_policy(self) -> None:
        with patch.object(client, "received_object_values", return_value={6}):
            client.sync_object_availability(self.ctx, challenge_active=False)

        jumbo_record = self.records[6]
        girder_record = self.records[37]
        self.assertEqual(0, self.fake.read_u32(jumbo_record + 0x0C))
        self.assertEqual(0, self.fake.read_u32(jumbo_record + 0x14))
        self.assertEqual(0, self.fake.read_u32(jumbo_record + 0x2C))
        self.assertEqual(client.OBJECT_LOCK_THRESHOLD, self.fake.read_u32(girder_record + 0x2C))
        self.assertEqual(0, self.fake.read_u32(girder_record + 0x0C))

    def test_object_resync_is_deferred_inside_challenge(self) -> None:
        owned_object_id = 6
        owned_record = self.records[owned_object_id]
        self.fake.write_u32(owned_record + 0x0C, 1)
        self.fake.write_u32(owned_record + 0x14, 1)
        self.fake.write_u32(owned_record + 0x2C, client.OBJECT_LOCK_THRESHOLD)

        with patch.object(client, "received_object_values", return_value={owned_object_id}):
            client.sync_object_availability(self.ctx, challenge_active=True)

        self.assertTrue(self.ctx._object_resync_pending)
        self.assertEqual({}, self.ctx._object_records)
        self.assertEqual(1, self.fake.read_u32(owned_record + 0x0C))
        self.assertEqual(1, self.fake.read_u32(owned_record + 0x14))
        self.assertEqual(client.OBJECT_LOCK_THRESHOLD, self.fake.read_u32(owned_record + 0x2C))

        with patch.object(client, "received_object_values", return_value={owned_object_id}):
            client.sync_object_availability(self.ctx, challenge_active=False)

        self.assertFalse(self.ctx._object_resync_pending)
        self.assertEqual(0, self.fake.read_u32(owned_record + 0x0C))
        self.assertEqual(0, self.fake.read_u32(owned_record + 0x14))
        self.assertEqual(0, self.fake.read_u32(owned_record + 0x2C))
        self.assertEqual(client.OBJECT_LOCK_THRESHOLD, self.fake.read_u32(self.records[37] + 0x2C))

    def test_contraption_patch_is_guarded_by_original_opcode(self) -> None:
        patch_data = self.ctx.slot_data["ram"]["object_system"]["contraption_patch"]
        address = int(patch_data["address"], 0)
        original = int(patch_data["original"], 0)
        patched = int(patch_data["patched"], 0)
        self.fake.write_u32(address, original)

        client.ensure_contraption_patch(self.ctx, challenge_active=False)

        self.assertEqual(patched, self.fake.read_u32(address))

    def test_contraption_patch_skips_unknown_opcode(self) -> None:
        patch_data = self.ctx.slot_data["ram"]["object_system"]["contraption_patch"]
        address = int(patch_data["address"], 0)
        self.fake.write_u32(address, 0x12345678)

        client.ensure_contraption_patch(self.ctx, challenge_active=False)

        self.assertEqual(0x12345678, self.fake.read_u32(address))

    def test_local_challenge_palette_hides_unowned_entry_plus_four(self) -> None:
        current_world_address = int(game_data.RAM_ADDRESSES["current_world_id"]["address"], 0)
        current_challenge_address = int(game_data.RAM_ADDRESSES["current_challenge_index"]["address"], 0)
        lead_address = int(game_data.RAM_MAP["object_system"]["challenge_object_root_lead"], 0)
        root = 0x80640000
        list_container = 0x912F0000
        entries = 0x912F1000
        self.fake.write_byte(current_world_address, 2)
        self.fake.write_byte(current_challenge_address, 0)
        self.fake.write_u32(lead_address, root)
        self.fake.write_u32(root + client.OBJECT_LIST_OFFSET, list_container)
        self.fake.write_u32(list_container, entries)
        self.fake.write_u32(list_container + 0x04, 1)
        self.fake.write_u32(entries + 0x04, 0xDEADBEEF)

        with patch.object(client, "received_object_values", return_value=set()):
            client.filter_current_challenge_palette(self.ctx, challenge_active=True)

        self.assertEqual(0, self.fake.read_u32(entries + 0x04))
        self.assertEqual(0, self.fake.read_u32(entries))

        client.filter_current_challenge_palette(self.ctx, challenge_active=False)

        with patch.object(client, "received_object_values", return_value={6}):
            client.filter_current_challenge_palette(self.ctx, challenge_active=True)

        self.assertEqual(0xDEADBEEF, self.fake.read_u32(entries + 0x04))

    def test_total_sparks_displays_ap_spark_count_when_required_sparks_enabled(self) -> None:
        total_sparks_address = int(game_data.RAM_ADDRESSES["total_sparks"]["address"], 0)
        self.fake.write_u32(total_sparks_address, 123)

        with patch.object(client, "received_spark_count", return_value=516):
            client.sync_total_sparks(self.ctx)

        self.assertEqual(516, self.fake.read_u32(total_sparks_address))

    def test_total_sparks_is_not_written_when_required_sparks_disabled(self) -> None:
        total_sparks_address = int(game_data.RAM_ADDRESSES["total_sparks"]["address"], 0)
        self.fake.write_u32(total_sparks_address, 123)
        self.ctx.slot_data["required_sparks"] = 0

        with patch.object(client, "received_spark_count", return_value=516):
            client.sync_total_sparks(self.ctx)

        self.assertEqual(123, self.fake.read_u32(total_sparks_address))

    def test_unowned_world_access_is_relocked_to_zero(self) -> None:
        current_world_address = int(game_data.RAM_ADDRESSES["current_world_id"]["address"], 0)
        access_address = int(game_data.CHALLENGE_RECORDS[1]["access"], 16)
        self.fake.write_byte(current_world_address, 1)
        self.fake.write_byte(access_address, 1)

        with patch.object(client, "received_world_keys", return_value=set()):
            client.sync_world_access(self.ctx)

        self.assertEqual(0, self.fake.read_byte(access_address))

    def test_unowned_ii_world_access_trio_is_relocked_to_zero(self) -> None:
        current_world_address = int(game_data.RAM_ADDRESSES["current_world_id"]["address"], 0)
        self.fake.write_byte(current_world_address, 1)
        for raw_address in game_data.II_WORLD_FLAGS_BY_NAME["Theme Park II"]:
            self.fake.write_byte(int(raw_address, 16), 1)

        with patch.object(client, "received_world_keys", return_value=set()):
            client.sync_world_access(self.ctx)

        for raw_address in game_data.II_WORLD_FLAGS_BY_NAME["Theme Park II"]:
            self.assertEqual(0, self.fake.read_byte(int(raw_address, 16)))

    def test_owned_world_access_waits_for_hub_chain_completion(self) -> None:
        current_world_address = int(game_data.RAM_ADDRESSES["current_world_id"]["address"], 0)
        access_address = int(game_data.CHALLENGE_RECORDS[1]["access"], 16)
        hub_chain_location_id = 23456
        self.ctx.slot_data["locations"]["Hub World Create Chain"] = {"id": hub_chain_location_id}
        self.fake.write_byte(current_world_address, 1)

        with patch.object(client, "received_world_keys", return_value={"W02"}):
            client.sync_world_access(self.ctx)
            self.assertEqual(0, self.fake.read_byte(access_address))

            self.ctx.locations_checked.add(hub_chain_location_id)
            client.sync_world_access(self.ctx)

        self.assertEqual(1, self.fake.read_byte(access_address))

    def test_create_chain_check_uses_chain_specific_completion(self) -> None:
        current_world_address = int(game_data.RAM_ADDRESSES["current_world_id"]["address"], 0)
        chain_index_address = int(game_data.RAM_ADDRESSES["create_chain_index"]["address"], 0)
        chain_completion_address = int(game_data.RAM_ADDRESSES["create_chain_completion"]["address"], 0)
        generic_completion_address = int(game_data.RAM_ADDRESSES["generic_completion_event"]["address"], 0)
        location_name = "Theme Park Create Chain 1"
        self.ctx.slot_data["locations"][location_name] = {"id": 12345}
        self.ctx.slot_data["worlds"]["W01"]["name"] = "Theme Park"
        self.ctx._chain_events_seen = set()
        self.ctx._chain_completion_context = None
        self.ctx._previous_chain_completion = None
        self.ctx._chain_context_ready_at = 0.0
        newly_checked: set[int] = set()
        self.fake.write_byte(current_world_address, 2)
        self.fake.write_byte(chain_index_address, 0)
        self.fake.write_byte(chain_completion_address, 0)
        self.fake.write_byte(generic_completion_address, 7)

        with patch.object(client.time, "monotonic", return_value=10.0):
            client.check_create_chain(self.ctx, newly_checked)
        with patch.object(client.time, "monotonic", return_value=13.0):
            client.check_create_chain(self.ctx, newly_checked)
        self.fake.write_byte(chain_completion_address, 1)
        with patch.object(client.time, "monotonic", return_value=14.0):
            client.check_create_chain(self.ctx, newly_checked)

        self.assertEqual({12345}, newly_checked)

    def test_hub_parts_require_full_sequence_for_part_three(self) -> None:
        world_address = int(game_data.RAM_ADDRESSES["current_world_id"]["address"], 0)
        part_address = int(game_data.RAM_ADDRESSES["hub_create_chain_part"]["address"], 0)
        self.fake.write_byte(world_address, 1)
        for part in range(1, 4):
            self.ctx.slot_data["locations"][f"Hub World Create Chain Part {part}"] = {"id": 9000 + part}
        for sequence, expected in (
            ([3], set()),
            ([1, 2, 3], {9001, 9002}),
            ([0, 2, 3], {9002}),
            ([0, 1, 0, 2, 3], {9001, 9002}),
            ([0, 0, 1, 1, 2, 2, 3, 3], {9001, 9002, 9003}),
            ([0, 1, 2, 7], {9001, 9002, 9003}),
        ):
            with self.subTest(sequence=sequence):
                self.ctx.locations_checked.clear()
                self.ctx._hub_chain_part_sequence = None
                checked = set()
                for value in sequence:
                    self.fake.write_byte(part_address, value)
                    client.check_hub_create_chain_parts(self.ctx, checked)
                self.assertEqual(expected, checked)

    def test_hub_create_chain_triggers_first_time_hub_challenge_is_entered(self) -> None:
        current_world_address = int(game_data.RAM_ADDRESSES["current_world_id"]["address"], 0)
        challenge_address = int(game_data.RAM_ADDRESSES["current_challenge_index"]["address"], 0)
        self.ctx.slot_data["locations"]["Hub World Create Chain"] = {"id": 23456}
        self.ctx.slot_data["locations"]["Starting World Unlock"] = {"id": 23457}
        self.fake.write_byte(current_world_address, 1)
        newly_checked: set[int] = set()

        self.fake.write_byte(challenge_address, 9)
        client.check_create_chain(self.ctx, newly_checked)
        self.assertEqual(set(), newly_checked)

        self.fake.write_byte(challenge_address, 10)
        client.check_create_chain(self.ctx, newly_checked)
        self.assertEqual({23456, 23457}, newly_checked)

        newly_checked.clear()
        client.check_create_chain(self.ctx, newly_checked)
        self.assertEqual(set(), newly_checked)

    def test_hub_create_chain_ignores_reward_pulses_outside_hub_challenge(self) -> None:
        current_world_address = int(game_data.RAM_ADDRESSES["current_world_id"]["address"], 0)
        completion_address = int(game_data.RAM_ADDRESSES["create_chain_completion"]["address"], 0)
        self.ctx.slot_data["locations"]["Hub World Create Chain"] = {"id": 23456}
        self.fake.write_byte(current_world_address, 1)
        self.fake.write_byte(int(game_data.RAM_ADDRESSES["current_challenge_index"]["address"], 0), 9)
        newly_checked: set[int] = set()

        for value in (0, 1, 0, 1, 0, 1):
            self.fake.write_byte(completion_address, value)
            client.check_create_chain(self.ctx, newly_checked)

        self.assertEqual(set(), newly_checked)

    def test_hub_create_chain_recovers_completed_check_after_restart(self) -> None:
        current_world_address = int(game_data.RAM_ADDRESSES["current_world_id"]["address"], 0)
        challenge_address = int(game_data.RAM_ADDRESSES["current_challenge_index"]["address"], 0)
        self.ctx.slot_data["locations"]["Hub World Create Chain"] = {"id": 23456}
        self.fake.write_byte(current_world_address, 1)
        self.fake.write_byte(challenge_address, 10)
        newly_checked: set[int] = set()

        client.check_create_chain(self.ctx, newly_checked)

        self.assertEqual({23456}, newly_checked)

    def test_slot_selection_cooldown_is_five_seconds(self) -> None:
        self.ctx._reset_ram_baselines = Mock()
        with patch.object(client.time, "monotonic", return_value=100.0):
            client.CreateContext.start_slot_settle(self.ctx)
        self.assertEqual(105.0, self.ctx._slot_ready_at)
        with patch.object(client.time, "monotonic", return_value=104.9):
            self.assertFalse(client.CreateContext.slot_ram_is_settled(self.ctx))
        with patch.object(client.time, "monotonic", return_value=105.0):
            self.assertTrue(client.CreateContext.slot_ram_is_settled(self.ctx))

    def test_slot_settle_wait_is_silent(self) -> None:
        self.ctx._slot_ready_at = 10.0

        with patch.object(client.time, "monotonic", return_value=9.0):
            with patch.object(client.logger, "info") as info:
                self.assertFalse(client.CreateContext.slot_ram_is_settled(self.ctx))

        info.assert_not_called()

    def test_hub_challenge_reward_requires_zero_baseline(self) -> None:
        current_world_address = int(game_data.RAM_ADDRESSES["current_world_id"]["address"], 0)
        current_challenge_address = int(game_data.RAM_ADDRESSES["current_challenge_index"]["address"], 0)
        current_sparks_address = int(game_data.RAM_ADDRESSES["current_challenge_sparks"]["address"], 0)
        location_name = "Hub World Challenge 1 - Reward"
        self.ctx.slot_data["locations"][location_name] = {"id": 34567}
        self.fake.write_byte(current_world_address, 1)
        self.fake.write_byte(current_challenge_address, 10)
        newly_checked: set[int] = set()

        self.fake.write_byte(current_sparks_address, 1)
        with patch.object(client.time, "monotonic", return_value=100.0):
            client.check_challenge_sparks(self.ctx, newly_checked)
        self.fake.write_byte(current_sparks_address, 0)
        with patch.object(client.time, "monotonic", return_value=101.0):
            client.check_challenge_sparks(self.ctx, newly_checked)
        self.fake.write_byte(current_sparks_address, 1)
        with patch.object(client.time, "monotonic", return_value=102.0):
            client.check_challenge_sparks(self.ctx, newly_checked)

        self.assertEqual({34567}, newly_checked)

    def test_spark_count_alone_does_not_write_goal_world_access(self) -> None:
        current_world_address = int(game_data.RAM_ADDRESSES["current_world_id"]["address"], 0)
        goal_world_access = int(game_data.CHALLENGE_RECORDS[6]["access"], 16)
        self.fake.write_byte(current_world_address, 1)
        self.fake.write_byte(goal_world_access, 0)

        with patch.object(client, "received_world_keys", return_value=set()):
            client.sync_world_access(self.ctx)

        self.assertEqual(0, self.fake.read_byte(goal_world_access))

    def test_spark_requirement_sends_real_location_check(self) -> None:
        self.ctx.slot_data["locations"]["Spark Requirement Met"] = {"id": 45678}
        newly_checked: set[int] = set()

        with patch.object(client, "received_spark_count", return_value=516):
            client.check_spark_goal_world_unlock(self.ctx, newly_checked)

        self.assertEqual({45678}, newly_checked)


class TestCreateVictory(unittest.TestCase):
    def test_spark_hunt_threshold_and_single_goal_notification(self) -> None:
        for mode, required, received, victory, expected in (
            ("spark_hunt", 0, 0, False, False),
            ("spark_hunt", 0, 0, True, True),
            ("goal_world_unlock", 0, 0, False, False),
            ("goal_world_unlock", 0, 0, True, True),
            ("spark_hunt", 3, 2, False, False),
            ("spark_hunt", 3, 3, False, True),
        ):
            with self.subTest(mode=mode, required=required, received=received, victory=victory):
                ctx = SimpleNamespace(
                    finished_game=False,
                    slot_data={"spark_goal_mode": mode, "required_sparks": required},
                    send_msgs=Mock(return_value=None),
                )
                with patch.object(client, "received_spark_count", return_value=received), \
                        patch.object(client, "received_item_names", return_value={client.ITEM_VICTORY} if victory else set()), \
                        patch.object(client.Utils, "async_start"):
                    client.process_victory(ctx)
                    client.process_victory(ctx)
                self.assertEqual(expected, ctx.finished_game)
                if expected:
                    ctx.send_msgs.assert_called_once_with([
                        {"cmd": "StatusUpdate", "status": client.ClientStatus.CLIENT_GOAL}
                    ])
                else:
                    ctx.send_msgs.assert_not_called()


class TestCreateSaveSlotGuard(unittest.TestCase):
    def setUp(self):
        self.fake = install_fake_dolphin()
        self.ctx = make_context()
        self.ctx.save_slot_armed = False
        self.ctx._slot_guard_observed_this_session = False
        self.ctx._slot_ready_at = 0.0
        self.ctx._slot_settle_logged = False
        self.ctx._slot_connected_logged = False
        self.ctx._waiting_for_slot_logged = False
        self.ctx._reset_ram_baselines = Mock()
        self.ctx.start_slot_settle = types.MethodType(client.CreateContext.start_slot_settle, self.ctx)
        self.ctx.slot_ram_is_settled = types.MethodType(client.CreateContext.slot_ram_is_settled, self.ctx)
        self.guard = client._address(self.ctx.slot_data["ram"]["addresses"]["save_slot_guard_primary"])

    def sync(self, value, now):
        self.fake.write_byte(self.guard, value)
        with patch.object(client.time, "monotonic", return_value=now):
            client.sync_save_slot_guard(self.ctx)

    def test_ff_requires_positive_observation(self):
        self.sync(255, 100)
        self.assertFalse(self.ctx.save_slot_armed)
        self.assertFalse(self.ctx._slot_guard_observed_this_session)

    def test_two_starts_settle_and_ff_only_arms_after_deadline(self):
        self.sync(2, 100)
        self.assertTrue(self.ctx._slot_guard_observed_this_session)
        self.assertEqual(105, self.ctx._slot_ready_at)
        self.assertFalse(self.ctx.save_slot_armed)
        self.ctx._reset_ram_baselines.assert_called_once()
        self.sync(255, 104)
        self.assertFalse(self.ctx.save_slot_armed)
        self.sync(255, 105)
        self.assertTrue(self.ctx.save_slot_armed)
        self.assertEqual(135, self.ctx._hub_event_ready_at)

    def test_invalid_guard_revokes_success_and_requires_new_settle(self):
        self.sync(2, 100)
        self.sync(2, 105)
        self.assertTrue(self.ctx.save_slot_armed)
        self.sync(0, 106)
        self.assertFalse(self.ctx.save_slot_armed)
        self.assertFalse(self.ctx._slot_guard_observed_this_session)
        self.assertEqual(0, self.ctx._slot_ready_at)
        self.assertFalse(self.ctx._slot_connected_logged)
        self.sync(255, 107)
        self.assertFalse(self.ctx.save_slot_armed)
        self.sync(2, 108)
        self.assertEqual(113, self.ctx._slot_ready_at)
        self.assertFalse(self.ctx.save_slot_armed)

    def test_reconnect_cannot_arm_from_previous_success(self):
        self.sync(2, 100)
        self.sync(2, 105)
        client.CreateContext.on_package(self.ctx, "Connected", {"slot_data": self.ctx.slot_data})
        self.sync(255, 110)
        self.assertFalse(self.ctx.save_slot_armed)
        self.sync(0, 111)
        self.assertFalse(self.ctx.save_slot_armed)

    def test_dolphin_rehook_revokes_guard_observation(self):
        self.sync(2, 100)
        self.sync(2, 105)
        client.CreateContext.start_ram_settle(self.ctx)
        self.sync(255, 110)
        self.assertFalse(self.ctx.save_slot_armed)

    def test_failed_read_revokes_guard_observation(self):
        self.sync(2, 100)
        self.sync(2, 105)
        with patch.object(client, "read_u8", side_effect=RuntimeError("unhooked")):
            client.sync_save_slot_guard(self.ctx)
        self.sync(255, 110)
        self.assertFalse(self.ctx.save_slot_armed)


def execute_popup_ppc(runtime, memory, entry, registers, *, lr=0x81230000, native=None):
    """Small test CPU for this patch's integer/control/cache instructions.

    Native game calls are explicit test doubles; no UI execution is implied.
    Decode the emitted words rather than duplicating the patch's conditions.
    """
    regs, pc, cr, events = list(registers), entry, (False, False, False), []
    def signed(value, bits):
        return value - (1 << bits) if value & (1 << (bits - 1)) else value
    for _ in range(1024):
        in_primary = runtime.layout.code_base <= pc < runtime.layout.mailbox
        in_auxiliary = runtime.layout.aux_base <= pc < runtime.layout.aux_end
        if not (in_primary or in_auxiliary):
            if native and pc in native:
                events.append(("call", pc))
                native[pc](regs)
                pc = lr
                continue
            return pc, regs, cr[2], events
        if in_primary:
            offset = pc - runtime.layout.code_base
            ins = int.from_bytes(runtime.image[offset:offset + 4], "big")
        else:
            offset = pc - runtime.layout.aux_base
            ins = int.from_bytes(runtime.aux_image[offset:offset + 4], "big")
        source = pc
        pc += 4
        op, rt, ra, rb = ins >> 26, (ins >> 21) & 31, (ins >> 16) & 31, (ins >> 11) & 31
        imm, xo = signed(ins & 0xFFFF, 16), (ins >> 1) & 1023
        if op == 7:
            regs[rt] = (regs[ra] * imm) & 0xFFFFFFFF
        elif op in (13, 14, 15):
            left = regs[ra] if op == 13 or ra else 0
            regs[rt] = (left + (imm << (16 if op == 15 else 0))) & 0xFFFFFFFF
            if op == 13:
                cr = (bool(regs[rt] & 0x80000000), regs[rt] != 0 and not bool(regs[rt] & 0x80000000), regs[rt] == 0)
        elif op == 28:
            regs[ra] = regs[rt] & (ins & 0xFFFF)
            cr = (bool(regs[ra] & 0x80000000), regs[ra] != 0 and not bool(regs[ra] & 0x80000000), regs[ra] == 0)
        elif op == 24:
            regs[ra] = regs[rt] | (ins & 0xFFFF)
        elif op in (32, 34):
            address = ((regs[ra] if ra else 0) + imm) & 0xFFFFFFFF
            regs[rt] = int.from_bytes(memory.read_bytes(address, 4 if op == 32 else 1), "big")
        elif op in (36, 37, 38):
            address = ((regs[ra] if ra else 0) + imm) & 0xFFFFFFFF
            if op == 38:
                memory.write_byte(address, regs[rt] & 255)
            else:
                memory.write_u32(address, regs[rt])
            events.append(("store", address, regs[rt]))
            if op == 37:
                regs[ra] = address
        elif op in (10, 11) or op == 31 and xo in (0, 32):
            left = regs[ra]
            right = (ins & 0xFFFF if op == 10 else imm & 0xFFFFFFFF) if op in (10, 11) else regs[rb]
            if op == 11 or op == 31 and xo == 0:
                left, right = signed(left, 32), signed(right, 32)
            cr = (left < right, left > right, left == right)
        elif op == 31 and xo == 40:
            regs[rt] = (regs[rb] - regs[ra]) & 0xFFFFFFFF
        elif op == 31 and xo == 459:
            regs[rt] = regs[ra] // regs[rb]
        elif op == 31 and xo == 444:
            regs[ra] = regs[rt] | regs[rb]
        elif ins == 0x7C0802A6:
            regs[0] = lr
        elif ins == 0x7C0803A6:
            lr = regs[0]
        elif ins == 0x4CC63182:
            pass  # variadic call CR1 flag
        elif ins in (0x7C0004AC, 0x4C00012C):
            events.append(("sync" if ins == 0x7C0004AC else "isync",))
        elif op == 31 and xo in (54, 982):
            events.append(("dcbst" if xo == 54 else "icbi", ((regs[ra] if ra else 0) + regs[rb]) & ~31))
        elif op == 18:
            assert not ins & 2
            if ins & 1:
                lr = pc
            pc = source + signed(ins & 0x03FFFFFC, 26)
        elif op == 16:
            assert ra in (0, 1, 2) and rt in (4, 12)
            if cr[ra] == (rt == 12):
                pc = source + signed(ins & 0xFFFC, 16)
        elif ins in (0x4D820020, 0x4C820020):
            if cr[2] == (ins == 0x4D820020):
                pc = lr
        elif ins == 0x4E800020:
            pc = lr
        else:
            raise AssertionError(f"Unsupported PPC instruction {ins:08X} at {source:08X}")
    raise AssertionError("Popup code did not return")


def seed_popup_memory(memory):
    for address, value in {**popup.ORIGINALS, **popup.LEGACY_ORIGINALS,
                            popup.GAME_SINGLETON: popup.GAME_VTABLE}.items():
        memory.write_u32(address, value)


def apply_guest_popup_hooks(runtime, memory):
    execute_popup_ppc(runtime, memory, runtime.layout.maintain_hooks, [0] * 32)


class TestCreatePopupRuntime(unittest.TestCase):
    def setUp(self):
        self.fake = FakeDolphinMemoryEngine()
        self.runtime = popup.PopupRuntime()
        self.read = self.fake.read_bytes
        self.writes = []
        self.base = self.runtime.layout.mailbox
        seed_popup_memory(self.fake)

    def write(self, address, data):
        self.writes.append((address, data))
        self.fake.write_bytes(address, data)

    def install(self):
        self.assertFalse(self.runtime.ensure_installed(self.read, self.write))
        self.assertTrue(self.runtime.installed)
        apply_guest_popup_hooks(self.runtime, self.fake)
        self.fake.write_u32(self.base + 0x1C, 1)
        self.assertTrue(self.runtime.ensure_installed(self.read, self.write))

    def test_branch_encoder(self):
        self.assertEqual(0x4808A365, popup.ppc_branch(0x8000DB5C, 0x80097EC0, link=True))
        self.assertEqual(0x4BFFFFFC, popup.ppc_branch(0x1004, 0x1000))
        self.assertEqual(0x49FFFFFC, popup.ppc_branch(0, 0x1FFFFFC))
        self.assertEqual(0x4A000000, popup.ppc_branch(0x2000000, 0))
        for source, target in ((0, 1), (1, 5), (0, 0x2000000), (0x2000004, 0)):
            with self.subTest(source=source, target=target), self.assertRaises(ValueError):
                popup.ppc_branch(source, target)

    def test_python_installs_only_cave_and_vtable_data_pointer(self):
        self.runtime.ensure_installed(self.read, self.write)
        self.assertTrue(self.runtime.installed)
        self.assertEqual([self.runtime.layout.aux_base, self.runtime.layout.code_base,
                          self.base + 0x44, popup.VTABLE_SLOT],
                         [a for a, _ in self.writes])
        for address, original in popup.CODE_ORIGINALS.items():
            self.assertEqual(original, self.fake.read_u32(address))
        self.assertEqual(self.runtime.layout.dispatcher, self.fake.read_u32(popup.VTABLE_SLOT))
        self.assertFalse(self.runtime.ready)

    def test_guest_installs_and_flushes_only_results_availability_hook(self):
        self.runtime.ensure_installed(self.read, self.write)
        _, _, _, events = execute_popup_ppc(self.runtime, self.fake,
                                            self.runtime.layout.maintain_hooks, [0] * 32)
        for address in popup.CODE_ORIGINALS:
            self.assertEqual(self.runtime.hooks[address], self.fake.read_u32(address))
            self.assertIn(("dcbst", address & ~31), events)
            self.assertIn(("icbi", address & ~31), events)
        self.assertEqual(1, sum(e[0] == "icbi" for e in events))
        self.assertLess(events.index(("isync",)), events.index(("store", self.base + 0x48, 1)))

    def test_installs_results_context_and_native_owner_cleanup(self):
        self.install()
        self.assertEqual(self.runtime.layout.aux_base, self.writes[0][0])
        self.assertEqual(self.runtime.layout.code_base, self.writes[1][0])
        self.assertEqual(0x80074D90, self.fake.read_u32(self.base + 0x38))
        self.assertEqual(self.base + 0x20, self.fake.read_u32(self.base + 0x3C))
        self.assertEqual(self.runtime.layout.closed_callback, self.fake.read_u32(self.base + 0x2C))
        context = self.runtime.layout.result_context
        self.assertEqual(bytes(16) + popup.word(1) + bytes(4), self.read(context, 24))

    def test_refuses_unexpected_instruction_without_writing(self):
        self.fake.write_u32(0x800325E4, 0x12345678)
        self.assertFalse(self.runtime.ensure_installed(self.read, self.write))
        self.assertEqual([], self.writes)
        self.assertIn("unexpected instruction", self.runtime.failure)

    def test_refuses_unknown_cave_even_with_valid_signature(self):
        for signature in (False, True):
            with self.subTest(signature=signature):
                self.setUp()
                if signature:
                    self.fake.write_bytes(self.runtime.layout.code_base, self.runtime.image)
                self.fake.write_u32(self.runtime.layout.code_base, 0x12345678)
                self.assertFalse(self.runtime.ensure_installed(self.read, self.write))
                self.assertEqual([], self.writes)

    def test_refuses_unknown_auxiliary_cave_without_writing(self):
        self.fake.write_u32(self.runtime.layout.aux_base, 0x12345678)
        self.assertFalse(self.runtime.ensure_installed(self.read, self.write))
        self.assertEqual([], self.writes)
        self.assertIn("auxiliary", self.runtime.failure)

    def test_adopts_exact_patch_without_overwriting_live_owner(self):
        self.install()
        self.fake.write_u32(self.base + 8, popup.ACTIVE)
        self.fake.write_u32(self.base + 0x20, 0x81234560)
        before = self.read(self.base, 0x48)
        replacement = popup.PopupRuntime()
        replacement.ensure_installed(self.read, self.write)
        self.assertTrue(replacement.installed)
        self.assertEqual(before, self.read(self.base, 0x48))

    def test_uninstall_cancels_then_guest_flushes_before_vtable_detach(self):
        self.install()
        self.assertTrue(self.runtime.request_object(13, self.read, self.write))
        self.writes.clear()
        self.runtime.uninstall(self.read, self.write)
        self.assertEqual([self.base + 8, self.base + 0x44], [a for a, _ in self.writes])
        self.assertEqual(self.runtime.layout.dispatcher, self.fake.read_u32(popup.VTABLE_SLOT))
        _, _, _, events = execute_popup_ppc(self.runtime, self.fake,
                                            self.runtime.layout.maintain_hooks, [0] * 32)
        for address, value in popup.ORIGINALS.items():
            self.assertEqual(value, self.fake.read_u32(address))
        self.assertLess(events.index(("isync",)),
                        events.index(("store", popup.VTABLE_SLOT, popup.ORIGINAL_UPDATE)))
        self.assertNotEqual(bytes(20), self.read(self.runtime.layout.closed_callback, 20))

    def test_requests_validate_range_busy_state_and_publish_last(self):
        self.assertFalse(self.runtime.request_object(13, self.read, self.write))
        self.install()
        for value in (-1, 262, "13"):
            self.assertFalse(self.runtime.request_object(value, self.read, self.write))
        self.writes.clear()
        self.assertTrue(self.runtime.request_object(13, self.read, self.write))
        self.assertEqual((self.base + 8, b"\0\0\0\1"), self.writes[-1])
        state = self.runtime.snapshot(self.read)
        self.assertEqual((13, 1, popup.PENDING), (state["object_id"], state["request_seq"], state["status"]))
        for status in (popup.PENDING, popup.ACTIVE, popup.ERROR):
            self.fake.write_u32(self.base + 8, status)
            self.assertFalse(self.runtime.request_object(6, self.read, self.write))

    def test_uninstall_leaves_active_owner_for_vanilla_close_callback(self):
        self.install()
        self.fake.write_u32(self.base + 8, popup.ACTIVE)
        self.fake.write_u32(self.base + 0x20, 0x81234560)
        self.fake.write_byte(self.base + 0x34, 1)
        owner = self.read(self.base, 0x44)
        self.runtime.uninstall(self.read, self.write)
        apply_guest_popup_hooks(self.runtime, self.fake)
        self.assertEqual(owner, self.read(self.base, 0x44))

    def test_reinstall_cancels_abandoned_pending_request(self):
        self.install()
        self.runtime.request_object(13, self.read, self.write)
        replacement = popup.PopupRuntime()
        replacement.ensure_installed(self.read, self.write)
        self.assertEqual(popup.IDLE, replacement.status(self.read))

    def test_big_endian_status_heartbeat_and_sequence_wrap(self):
        self.install()
        self.fake.write_u32(self.base + 0x1C, 0x12345678)
        self.fake.write_u32(self.base + 0x10, 0xFFFFFFFF)
        self.assertEqual(0x12345678, self.runtime.heartbeat(self.read))
        self.assertTrue(self.runtime.request_object(13, self.read, self.write))
        self.assertEqual(0, self.runtime.snapshot(self.read)["request_seq"])
        self.assertEqual(popup.PENDING, self.runtime.status(self.read))

    def test_heartbeat_timeout_restores_originals_and_stops_retrying(self):
        with patch.object(popup.time, "monotonic", return_value=100):
            self.runtime.ensure_installed(self.read, self.write)
        with patch.object(popup.time, "monotonic", return_value=105):
            self.assertFalse(self.runtime.ensure_installed(self.read, self.write))
        self.assertIn("heartbeat missing", self.runtime.failure)
        self.assertEqual(0, self.runtime.snapshot(self.read)["enabled"])
        apply_guest_popup_hooks(self.runtime, self.fake)  # next game frame after resume
        for address, value in popup.ORIGINALS.items():
            self.assertEqual(value, self.fake.read_u32(address))
        count = len(self.writes)
        self.runtime.ensure_installed(self.read, self.write)
        self.assertEqual(count, len(self.writes))

    def test_fast_syncs_do_not_shorten_heartbeat_probe(self):
        with patch.object(popup.time, "monotonic", return_value=100):
            self.runtime.ensure_installed(self.read, self.write)
        with patch.object(popup.time, "monotonic", return_value=101):
            for _ in range(100):
                self.runtime.ensure_installed(self.read, self.write)
        self.assertTrue(self.runtime.installed)
        self.assertIsNone(self.runtime.failure)

    def test_manual_probe_can_confirm_late_heartbeat(self):
        self.runtime = popup.PopupRuntime(probe_timeout=120)
        with patch.object(popup.time, "monotonic", return_value=100):
            self.runtime.ensure_installed(self.read, self.write)
        with patch.object(popup.time, "monotonic", return_value=200):
            self.assertFalse(self.runtime.ensure_installed(self.read, self.write))
            self.assertIsNone(self.runtime.failure)
            apply_guest_popup_hooks(self.runtime, self.fake)
            self.fake.write_u32(self.base + 0x1C, 1)
            self.assertTrue(self.runtime.ensure_installed(self.read, self.write))
        # After confirmation the ordinary liveness timeout applies again.
        with patch.object(popup.time, "monotonic", return_value=205):
            self.assertFalse(self.runtime.ensure_installed(self.read, self.write))
        self.assertIn("heartbeat missing", self.runtime.failure)

    def test_diagnostics_distinguish_ram_patch_from_execution(self):
        self.runtime.ensure_installed(self.read, self.write)
        report = self.runtime.diagnostics(self.read)
        self.assertTrue(report["installed"])
        self.assertTrue(report["cave_matches"])
        self.assertFalse(report["ready"])
        pointer = report["hooks"][f"0x{popup.VTABLE_SLOT:08X}"]
        self.assertEqual(pointer["ram"], pointer["expected"])
        for address in popup.CODE_ORIGINALS:
            hook = report["hooks"][f"0x{address:08X}"]
            self.assertNotEqual(hook["ram"], hook["expected"])
        apply_guest_popup_hooks(self.runtime, self.fake)
        self.assertFalse(self.runtime.ensure_installed(self.read, self.write))  # still no heartbeat

    def test_guest_conflict_preserves_foreign_hook_and_removes_own_hooks(self):
        self.install()
        foreign = 0x12345678
        self.fake.write_u32(0x800325E4, foreign)
        apply_guest_popup_hooks(self.runtime, self.fake)
        self.assertEqual(5, self.runtime.snapshot(self.read)["error"])
        self.assertEqual(0, self.runtime.snapshot(self.read)["enabled"])
        apply_guest_popup_hooks(self.runtime, self.fake)
        self.assertEqual(foreign, self.fake.read_u32(0x800325E4))
        self.assertEqual(popup.ORIGINAL_UPDATE, self.fake.read_u32(popup.VTABLE_SLOT))

    def test_code_readback_failure_never_installs_hooks(self):
        def broken_write(address, data):
            self.write(address, data)
            if address == self.runtime.layout.code_base:
                self.fake.write_byte(address, 0)
        self.assertFalse(self.runtime.ensure_installed(self.read, broken_write))
        self.assertEqual([self.runtime.layout.aux_base, self.runtime.layout.code_base],
                         [a for a, _ in self.writes])

    def test_dispatcher_calls_original_simupdate_and_has_no_legacy_hooks(self):
        layout = self.runtime.layout
        self.assertLessEqual(layout.end, 0x80006514)
        self.assertEqual(layout.end - layout.code_base, len(self.runtime.image))
        self.assertEqual(popup.word(popup.ppc_branch(layout.dispatcher + 12, popup.ORIGINAL_UPDATE, link=True)),
                         self.runtime.image[12:16])
        self.assertEqual({popup.VTABLE_SLOT, 0x800325E4}, set(self.runtime.hooks))

    def dispatcher_frame(self, *, lookup_result=0x81204000, get_ok=True, set_ok=True,
                         hide_ok=True, item_count=1.0, visible_width=0.0,
                         preload_width=0.0, thumbnail_visible=True):
        regs = [0x10000000 + i * 0x100 for i in range(32)]
        regs[1], regs[3], regs[4] = 0x81700000, popup.GAME_SINGLETON, 0x81203000
        before = list(regs)
        def original_update(r):
            self.assertEqual(before[3:5], r[3:5])
            r[3] = 0x12345678
        def lookup(r):
            self.assertEqual((0x808D3440, 13), tuple(r[3:5]))
            r[3] = lookup_result
        def construct(r):
            self.assertEqual((self.base + 0x38, self.runtime.layout.result_context), tuple(r[3:5]))
            self.assertEqual(popup.ACTIVE, self.fake.read_u32(self.base + 8))
            self.assertEqual(0, self.fake.read_u32(r[4]))
            self.assertEqual(1, self.fake.read_u32(r[4] + 0x10))
            self.fake.write_u32(0x81206000 + 0x14, 0x80947F98)
            self.fake.write_u32(0x80947F98, 0x81208000)
            self.fake.write_u32(0x80947F98 + 4, 0x81209000)
            r[3] = 0x81206000
        def register(r):
            self.assertEqual((0x80947A30, 3, 0, 1), tuple(r[3:7]))
            self.assertEqual(0x81206000, self.fake.read_u32(self.base + 0x20))
        invokes = []
        def get_variable(r):
            self.assertEqual(0x81209000, r[3])
            self.assertEqual(bytes(4), self.read(r[4] + 4, 4))
            if r[5] == 0x805E29DC:
                self.fake.write_u32(r[4], 0x8120C000)
                self.fake.write_u32(r[4] + 4, 0x46)
                self.fake.write_u32(r[4] + 8, 0x8120D000)
                r[3] = int(get_ok)
            else:
                name = self.read(r[5], 100).split(b"\0")[0]
                if name.endswith(b"._visible"):
                    self.fake.write_u32(r[4] + 4, 2)
                    self.fake.write_byte(r[4] + 8, int(thumbnail_visible))
                else:
                    self.assertIn(name, (
                        b"mItemData.length",
                        b"mUnlockContainer.mUnlockFrame.mDropdown.mImageContainer._width",
                        b"mThumbnailContainer0._width"))
                    self.fake.write_u32(r[4] + 4, 5)
                    value = {b"mItemData.length": item_count,
                             b"mUnlockContainer.mUnlockFrame.mDropdown.mImageContainer._width": visible_width,
                             b"mThumbnailContainer0._width": preload_width}[name]
                    self.write(r[4] + 8, struct.pack(">d", value))
                r[3] = 1
        def set_variable(r):
            self.assertEqual(0, r[6])
            name = self.read(r[4], 100).split(b"\0")[0]
            if name == b"Event_UnlockFinished":
                self.assertEqual(0x46, self.fake.read_u32(r[5] + 4))
                r[3] = int(set_ok)
            else:
                self.assertEqual(b"mScreen._visible", name)
                self.assertEqual(2, self.fake.read_u32(r[5] + 4))
                self.assertEqual(0, self.fake.read_u32(r[5] + 8))
                r[3] = int(hide_ok)
        def release_value(r):
            self.assertEqual(0x8120C000, r[3])
            self.assertEqual(0x8120D000, r[5])
        def invoke(r):
            self.assertEqual(0x81209000, r[3])
            name = self.read(r[4], 100).split(b"\0")[0]
            invokes.append(name)
            self.assertIn(name, (
                b"_root.stop",
                b"_root.DeterminePlaySequence",
                b"_root.mUnlockContainer.mUnlockFrame.stop",
                b"_root.mUnlockContainer.mUnlockFrame.gotoAndStop",
                b"_root.mUnlockContainer.mUnlockFrame.play"))
            if name.endswith(b"gotoAndStop"):
                self.assertEqual(b"s\0", self.read(r[5], 2))
                self.assertEqual(b"Wait\0", self.read(r[6], 5))
            else:
                self.assertEqual(b"\0", self.read(r[5], 1))
            r[3] = 1
        pc, result, _, events = execute_popup_ppc(
            self.runtime, self.fake, self.runtime.layout.dispatcher, regs,
            native={popup.ORIGINAL_UPDATE: original_update, 0x80490BF0: lookup,
                    0x80031DB0: construct, 0x804EA4D0: register,
                    0x8027E73C: get_variable, 0x8027E864: set_variable,
                    0x802E6EFC: release_value, 0x8028DF30: invoke})
        self.assertEqual(0x81230000, pc)
        self.assertEqual(0x12345678, result[3])
        self.assertEqual(before[1], result[1])
        self.assertEqual(before[14:], result[14:])
        return events

    def prepare_dispatch(self):
        self.runtime.ensure_installed(self.read, self.write)
        self.fake.write_u32(self.base + 8, popup.PENDING)
        self.fake.write_u32(self.base + 0x0C, 13)
        self.fake.write_byte(0x80B1ABD3, 2)
        self.fake.write_u32(popup.OBJECT_REGISTRY_COUNT, 0x35C)
        self.fake.write_u32(0x81204000, 0x81205000)
        self.fake.write_u32(0x81205000 + 0x340, 1)

    def test_dispatcher_bootstraps_without_gecko_and_opens_during_challenge(self):
        self.prepare_dispatch()
        self.fake.write_byte(0x8068CFC3, 0)  # running challenge
        events = self.dispatcher_frame()
        creation_events = events
        self.assertEqual([popup.ORIGINAL_UPDATE, 0x80490BF0, 0x80031DB0, 0x804EA4D0,
                          0x8027E73C, 0x8027E864, 0x802E6EFC, 0x8027E864,
                          ],
                         [e[1] for e in events if e[0] == "call"])
        self.assertEqual(1, self.fake.read_u32(self.base + 0x24))
        events = self.dispatcher_frame(visible_width=128.0, preload_width=64.0)
        self.assertNotIn(("call", 0x8028DF30), events)
        report = self.runtime.lifecycle(self.read)
        self.assertEqual(1.0, report["movie_item_data_length"]["value"])
        self.assertEqual(128.0, report["visible_thumbnail_width"]["value"])
        self.assertEqual(64.0, report["preloaded_thumbnail_width"]["value"])
        self.assertTrue(report["visible_thumbnail_container_visible"]["value"])
        self.assertLess(creation_events.index(("isync",)),
                        creation_events.index(("call", 0x80031DB0)))
        self.assertEqual(2, self.runtime.heartbeat(self.read))
        self.assertTrue(self.runtime.ensure_installed(self.read, self.write))

    def test_failed_event_binding_keeps_native_timeline_running(self):
        for get_ok, set_ok in ((False, True), (True, False)):
            with self.subTest(get_ok=get_ok, set_ok=set_ok):
                self.setUp()
                self.prepare_dispatch()
                events = self.dispatcher_frame(get_ok=get_ok, set_ok=set_ok)
                self.assertNotIn(("call", 0x8028DF30), events)
                self.assertIn(("call", 0x802E6EFC), events)
                self.assertEqual(0, self.fake.read_u32(self.base + 0x4C))
                self.assertEqual(0, self.fake.read_u32(self.base + 0x28))
                self.assertTrue(self.runtime._known_image(self.read(self.runtime.layout.code_base, len(self.runtime.image))))

    def test_failed_screen_hide_does_not_start_direct_sequence(self):
        self.prepare_dispatch()
        events = self.dispatcher_frame(hide_ok=False)
        self.assertNotIn(("call", 0x8028DF30), events)
        self.assertEqual(0, self.fake.read_u32(self.base + 0x28))
        for _ in range(4):
            events = self.dispatcher_frame()
            self.assertNotIn(("call", 0x8028DF30), events)

    def test_thumbnail_diagnostic_reads_metadata_without_mutation(self):
        self.prepare_dispatch()
        self.dispatcher_frame()
        self.fake.write_u32(0x81204018, 0x8120E000)
        self.fake.write_u32(0x8120E000, 0x8120F000)
        self.write(0x8120F000, b"AutomaticRocket\0")
        self.fake.write_u32(0x81206024, 1)
        self.dispatcher_frame()
        report = self.runtime.lifecycle(self.read)
        self.assertEqual("Thumb:AutomaticRocket", report["thumbnail_identifier_from_metadata"])
        self.assertEqual("AutomaticRocket", report["metadata_name"])
        self.assertEqual(1, report["unlock_count"])
        self.assertTrue(report["unlock_finished_handler_bound"])
        self.assertEqual(1, report["popup_phase"])
        self.assertTrue(report["show_unlock_called"])
        self.assertEqual(0.0, report["visible_thumbnail_width"]["value"])
        self.assertTrue(self.runtime._known_image(self.read(self.runtime.layout.code_base, len(self.runtime.image))))

    def test_native_preflight_defers_until_registry_and_descriptor_are_ready(self):
        for count, record, descriptor, unlockable in ((0, 0x81204000, 0x81205000, 1),
                                                     (13, 0x81204000, 0x81205000, 1),
                                                     (0x35C, 0, 0x81205000, 1),
                                                     (0x35C, 0x81204000, 0, 1),
                                                     (0x35C, 0x81204000, 0x81205000, 0)):
            with self.subTest(count=count, record=record, descriptor=descriptor, unlockable=unlockable):
                self.setUp()
                self.prepare_dispatch()
                self.fake.write_u32(popup.OBJECT_REGISTRY_COUNT, count)
                self.fake.write_u32(0x81204000, descriptor)
                self.fake.write_u32(0x81205000 + 0x340, unlockable)
                events = self.dispatcher_frame(lookup_result=record)
                self.assertNotIn(("call", 0x80031DB0), events)
                self.assertEqual(popup.PENDING, self.runtime.status(self.read))
                self.assertEqual(0, self.runtime.snapshot(self.read)["error"])

    def test_dispatcher_defers_for_modal_owner_and_invalid_save_guard(self):
        for address, value, byte in ((popup.MODAL_LAYER, 1, False),
                                     (self.base + 0x20, 0x81206000, False),
                                     (self.base + 0x34, 1, True),
                                     (0x80B1ABD3, 1, True)):
            with self.subTest(address=address):
                self.setUp()
                self.prepare_dispatch()
                if byte:
                    self.fake.write_byte(address, value)
                else:
                    self.fake.write_u32(address, value)
                events = self.dispatcher_frame()
                self.assertNotIn(("call", 0x80490BF0), events)
                self.assertEqual(popup.PENDING, self.runtime.status(self.read))

    def test_disabled_dispatcher_cleans_up_without_opening_pending_popup(self):
        self.prepare_dispatch()
        self.runtime.uninstall(self.read, self.write)
        events = self.dispatcher_frame()
        self.assertNotIn(("call", 0x80490BF0), events)
        self.assertEqual(popup.ORIGINAL_UPDATE, self.fake.read_u32(popup.VTABLE_SLOT))
        self.assertEqual(popup.IDLE, self.runtime.status(self.read))

    def test_dispatcher_never_closes_from_root_frame_or_invisibility(self):
        for frame, same_movie, expected in ((0, True, False), (365, True, False),
                                             (373, True, False), (374, False, False),
                                             (374, True, False)):
            with self.subTest(frame=frame, same_movie=same_movie):
                self.setUp()
                self.prepare_dispatch()
                self.fake.write_u32(self.base + 8, popup.ACTIVE)
                self.fake.write_u32(self.base + 0x10, 1)
                self.fake.write_u32(self.base + 0x20, 0x81206000)
                self.fake.write_u32(self.base + 0x40, 0x81209000 if same_movie else 0x8120A000)
                self.fake.write_u32(0x81206014, 0x80947F98)
                self.fake.write_u32(0x80947F9C, 0x81209000)
                self.fake.write_u32(0x81209064, 0x8120B000)
                self.fake.write_u32(0x8120B0BC, frame)
                regs = [0] * 32
                regs[1] = 0x81700000
                calls = []
                def close(r):
                    self.assertEqual(0x81206000, r[3])
                    self.assertEqual(1, self.fake.read_u32(self.base + 0x90))
                    calls.append(r[3])
                native = {popup.ORIGINAL_UPDATE: lambda r: None, 0x800336E0: close}
                for _ in range(2):
                    execute_popup_ppc(self.runtime, self.fake, self.runtime.layout.dispatcher, regs, native=native)
                self.assertEqual(int(expected), len(calls))
                self.assertEqual(0x81206000, self.fake.read_u32(self.base + 0x20))

    def test_lifecycle_reports_acknowledgement_and_native_movie_frame(self):
        self.install()
        self.fake.write_u32(self.base + 0x10, 7)
        self.fake.write_u32(self.base + 0x20, 0x81206000)
        self.fake.write_u32(0x81206014, 0x80947F98)
        self.fake.write_u32(0x80947F98, 1)
        self.fake.write_u32(0x80947F9C, 0x81209000)
        self.fake.write_u32(0x81209064, 0x8120B000)
        self.fake.write_u32(0x8120B0BC, 374)
        self.fake.write_u32(popup.MODAL_LAYER, 1)
        report = self.runtime.lifecycle(self.read)
        self.assertFalse(report["callback_invoked"])
        self.assertTrue(report["movie_slot_active"])
        self.assertEqual(374, report["root_frame_zero_based"])
        self.assertEqual(1, report["modal"])
        # Native End owns pointer/modal cleanup; the final AP callback only acks.
        self.fake.write_u32(self.base + 0x20, 0)
        self.fake.write_u32(popup.MODAL_LAYER, 0)
        regs = [0] * 32
        regs[3] = self.base
        execute_popup_ppc(self.runtime, self.fake, self.runtime.layout.closed_callback, regs)
        report = self.runtime.lifecycle(self.read)
        self.assertTrue(report["callback_invoked"])
        self.assertEqual(0, report["modal"])

    def test_refuses_previous_revision_and_wrong_singleton(self):
        for address in (0x8000DB5C, popup.GAME_SINGLETON):
            with self.subTest(address=address):
                self.setUp()
                self.fake.write_u32(address, 0x12345678)
                self.assertFalse(self.runtime.ensure_installed(self.read, self.write))
                self.assertEqual([], self.writes)

    def run_leaf_hook(self, entry, registers, *, lr=0x81230000):
        pc, regs, equal, _ = execute_popup_ppc(self.runtime, self.fake, entry, registers, lr=lr)
        return pc, regs, equal

    def hook_registers(self, *, status=popup.ACTIVE, ap_owner=True):
        regs = [0x10000000 + i * 0x100 for i in range(32)]
        regs[29], regs[25] = 0x81200000, 0x81200100
        owner = self.base + 0x20 if ap_owner else 0x81200200
        self.fake.write_u32(regs[29] + 0x20, owner)
        self.fake.write_u32(regs[25] + 4, owner)
        self.fake.write_u32(self.base + 8, status)
        self.fake.write_u32(self.base + 0x0C, 13)
        return regs

    def test_ap_availability_selects_only_target_regardless_of_threshold(self):
        for target, threshold in ((13, 0), (13, 0x7FFFFFFF), (6, 0), (6, 99)):
            with self.subTest(target=target, threshold=threshold):
                regs = self.hook_registers()
                regs[17], regs[7] = target, threshold
                destination, result, _ = self.run_leaf_hook(self.runtime.layout.object_available_hook, regs)
                self.assertEqual(0x81230000, destination)
                self.assertEqual(int(target == 13), result[3])
                self.assertEqual(regs[7], result[7])

    def test_ap_availability_skips_earlier_vanilla_candidates(self):
        regs = self.hook_registers()
        accepted = []
        for object_id in range(262):
            regs[17] = object_id
            _, result, _ = self.run_leaf_hook(self.runtime.layout.object_available_hook, regs)
            if result[3]:
                accepted.append(object_id)
        self.assertEqual([13], accepted)

    def test_vanilla_availability_preserved_during_other_popup(self):
        for status, owner in ((popup.IDLE, True), (popup.PENDING, True), (popup.ACTIVE, False)):
            with self.subTest(status=status, owner=owner):
                regs = self.hook_registers(status=status, ap_owner=owner)
                dest, result, _ = self.run_leaf_hook(self.runtime.layout.object_available_hook, regs)
                self.assertEqual(0x80025560, dest)
                self.assertEqual(regs[3:10], result[3:10])


class TestCreatePopupQueue(unittest.TestCase):
    def setUp(self):
        self.fake = install_fake_dolphin()
        self.ctx = make_context()
        self.ctx._popup_runtime = popup.PopupRuntime()
        self.ctx._popup_runtime_ready = False
        self.ctx._popup_accept_new_items = False
        self.ctx._popup_item_cursor = 0
        self.ctx._object_popup_queue = deque()
        self.ctx._automatic_object_popup_queue = deque()
        self.ctx._popup_inflight = None
        self.ctx._popup_inflight_automatic = None
        self.ctx._popup_last_status = None
        self.ctx._popup_delay_logged = False
        self.ctx._auto_popup_blocked_until = 0.0
        self.ctx._last_location_check_at = 0.0
        self.ctx._last_object_received_at = 0.0
        self.ctx._location_context_ready_at = 0.0
        self.ctx.ram_is_settled = lambda: True
        self.ctx.slot_ram_is_settled = lambda: True
        self.names = {value: name for name, data in self.ctx.slot_data["objects"].items()
                      for value in (int(data["global_value"]),)}
        self.lookup = patch.object(client, "item_name_from_network", side_effect=lambda ctx, item: self.names.get(item))
        self.lookup.start()
        self.addCleanup(self.lookup.stop)
        seed_popup_memory(self.fake)
        self.ctx._object_records = seed_object_registry(self.fake, self.ctx)
        self.ctx._object_resync_pending = False

    def receipt(self, value):
        self.ctx.items_received.append(SimpleNamespace(item=value))

    def ready(self):
        client.sync_object_popups(self.ctx, False)
        apply_guest_popup_hooks(self.ctx._popup_runtime, self.fake)
        self.fake.write_u32(self.ctx._popup_runtime.layout.mailbox + 0x1C, 1)
        client.sync_object_popups(self.ctx, False)

    def test_baseline_suppresses_history_and_keeps_receipt_order_duplicates(self):
        self.receipt(13)
        self.ready()
        self.assertEqual([], list(self.ctx._object_popup_queue))
        for value in (6, 99999, 13, 6):
            self.receipt(value)
        client.collect_new_object_popup_items(self.ctx)
        self.assertEqual([6, 13, 6], [value for value, _ in self.ctx._automatic_object_popup_queue])

    def test_real_receiveditems_queues_objects_once_and_preserves_history_baseline(self):
        self.receipt(13)
        client.CreateContext.on_package(self.ctx, "ReceivedItems", {"index": 0})
        self.assertEqual([], list(self.ctx._object_popup_queue))
        for value in (6, 99999, 13):
            self.receipt(value)
        client.CreateContext.on_package(self.ctx, "ReceivedItems", {"index": 1})
        self.assertEqual([6, 13], [value for value, _ in self.ctx._automatic_object_popup_queue])
        client.CreateContext.on_package(self.ctx, "ReceivedItems", {"index": 1})
        self.assertEqual([6, 13], [value for value, _ in self.ctx._automatic_object_popup_queue])
        self.ready()
        self.assertEqual((6, 1), self.ctx._popup_inflight)
        self.assertEqual([13], [value for value, _ in self.ctx._automatic_object_popup_queue])
        client.collect_new_object_popup_items(self.ctx)
        self.assertEqual([13], [value for value, _ in self.ctx._automatic_object_popup_queue])

    def test_challenge_dispatch_does_not_resolve_or_write_object_records(self):
        self.ready()
        self.receipt(13)
        record = self.ctx._object_records[13]
        client.apply_unowned_object_record(record)
        before = self.fake.read_bytes(record, 0x34)
        self.ctx._object_records = {}
        self.ctx._object_resync_pending = True
        with patch.object(client, "object_records", side_effect=AssertionError("MEM2 traversal")), \
             patch.object(client, "apply_owned_object_record", side_effect=AssertionError("threshold write")):
            client.sync_object_popups(self.ctx, True)
        self.assertIsNone(self.ctx._popup_inflight)
        self.assertEqual([13], [value for value, _ in self.ctx._automatic_object_popup_queue])
        self.assertEqual(before, self.fake.read_bytes(record, 0x34))

    def test_automatic_receipt_waits_for_event_grace_and_context_settle(self):
        self.ready()
        self.receipt(13)
        with patch.object(client.time, "monotonic", return_value=100.0):
            client.collect_new_object_popup_items(self.ctx)
        self.ctx._auto_popup_blocked_until = 102.0
        self.ctx._location_context_ready_at = 103.0
        with patch.object(client.time, "monotonic", return_value=102.5):
            client.service_object_popup_queue(self.ctx, False)
        self.assertIsNone(self.ctx._popup_inflight)
        with patch.object(client.time, "monotonic", return_value=103.0), \
             patch.object(client.logger, "info"):
            client.service_object_popup_queue(self.ctx, False)
        self.assertEqual((13, 1), self.ctx._popup_inflight)
        self.assertEqual((13, 100.0), self.ctx._popup_inflight_automatic)

    def test_queue_waits_for_close_and_modal_ui(self):
        self.ready()
        self.ctx._object_popup_queue.extend((13, 6))
        self.fake.write_u32(popup.MODAL_LAYER, 1)
        client.service_object_popup_queue(self.ctx, False)
        self.assertEqual([13, 6], list(self.ctx._object_popup_queue))
        self.fake.write_u32(popup.MODAL_LAYER, 0)
        client.service_object_popup_queue(self.ctx, False)
        client.service_object_popup_queue(self.ctx, False)
        self.assertEqual([6], list(self.ctx._object_popup_queue))
        base = self.ctx._popup_runtime.layout.mailbox
        self.fake.write_u32(base + 8, popup.IDLE)
        self.fake.write_u32(base + 0x14, 1)  # simulate mailbox written by close callback
        client.service_object_popup_queue(self.ctx, False)
        self.assertEqual((6, 2), self.ctx._popup_inflight)

    def test_challenge_transition_keeps_pending_request_for_native_preflight(self):
        self.ready()
        self.ctx._object_popup_queue.append(13)
        client.sync_object_popups(self.ctx, False)
        client.sync_object_popups(self.ctx, True)
        self.assertEqual(popup.PENDING, self.ctx._popup_runtime.status(client.read_memory))
        client.sync_object_popups(self.ctx, False)
        self.assertEqual((13, 1), self.ctx._popup_inflight)

    def test_dispatch_requires_settled_slot_but_not_python_object_sync(self):
        self.ctx._object_popup_queue.append(13)
        self.ctx.ram_is_settled = lambda: False
        client.sync_object_popups(self.ctx, True)
        self.assertFalse(self.ctx._popup_runtime.installed)
        self.ctx.ram_is_settled = lambda: True
        self.ctx._object_resync_pending = True
        self.ctx._object_records = {}
        client.sync_object_popups(self.ctx, True)
        self.assertTrue(self.ctx._popup_runtime.installed)
        self.assertTrue(self.ctx._popup_accept_new_items)
        apply_guest_popup_hooks(self.ctx._popup_runtime, self.fake)
        self.fake.write_u32(self.ctx._popup_runtime.layout.mailbox + 0x1C, 1)
        client.sync_object_popups(self.ctx, True)
        self.assertEqual((13, 1), self.ctx._popup_inflight)

    def test_manual_command_validates_slot_object_and_uses_shared_queue(self):
        processor = SimpleNamespace(ctx=self.ctx)
        for value in ("", "x", "-1", "262", "13 6"):
            client.CreateCommandProcessor._cmd_createpopup(processor, value)
        self.assertEqual([], list(self.ctx._object_popup_queue))
        self.assertEqual([], list(self.ctx._automatic_object_popup_queue))
        client.CreateCommandProcessor._cmd_createpopup(processor, "13")
        self.assertEqual([13], list(self.ctx._object_popup_queue))
        self.ready()
        self.assertEqual((13, 1), self.ctx._popup_inflight)

    def test_cache_command_explains_gecko_removal_without_touching_runtime(self):
        with patch.object(client.logger, "info") as log:
            client.CreateCommandProcessor._cmd_createpopupcache(SimpleNamespace(ctx=self.ctx))
        self.assertIn("needs no Gecko helper", log.call_args.args[0])
        self.assertFalse(self.ctx._popup_runtime.installed)

    def test_popup_session_reset_clears_receipts_queue_and_cancels_pending(self):
        self.ready()
        self.ctx._object_popup_queue.extend((13, 6))
        client.service_object_popup_queue(self.ctx, False)
        self.ctx.dolphin_status = client.CONNECTION_CONNECTED_STATUS
        client.CreateContext._reset_popup_state(self.ctx)
        self.assertFalse(self.ctx._popup_accept_new_items)
        self.assertIsNone(self.ctx._popup_inflight)
        self.assertEqual([], list(self.ctx._object_popup_queue))
        self.assertEqual(popup.IDLE, self.ctx._popup_runtime.status(client.read_memory))

    def test_receipt_during_heartbeat_probe_is_not_lost(self):
        client.sync_object_popups(self.ctx, False)
        self.receipt(13)
        apply_guest_popup_hooks(self.ctx._popup_runtime, self.fake)
        self.fake.write_u32(self.ctx._popup_runtime.layout.mailbox + 0x1C, 1)
        client.sync_object_popups(self.ctx, False)
        self.assertEqual((13, 1), self.ctx._popup_inflight)

    def test_manual_retry_preserves_queue_receipt_cursor_and_cancelled_request(self):
        self.ready()
        self.ctx._object_popup_queue.extend((13, 6))
        client.service_object_popup_queue(self.ctx, False)
        self.ctx._popup_item_cursor = 10
        self.ctx.dolphin_status = client.CONNECTION_CONNECTED_STATUS
        self.fake.write_byte(client._address(
            self.ctx.slot_data["ram"]["addresses"]["current_challenge_index"]), 255)
        client.CreateCommandProcessor._cmd_createpopupretry(SimpleNamespace(ctx=self.ctx))
        self.assertEqual([6], list(self.ctx._object_popup_queue))
        self.assertEqual((13, 1), self.ctx._popup_inflight)
        self.assertEqual(10, self.ctx._popup_item_cursor)
        self.assertEqual(120, self.ctx._popup_runtime.probe_timeout)
        self.assertFalse(self.ctx._popup_runtime_ready)
        self.assertEqual(popup.IDLE, self.ctx._popup_runtime.status(client.read_memory))

    def test_manual_retry_refuses_active_popup(self):
        self.ready()
        runtime = self.ctx._popup_runtime
        self.ctx.dolphin_status = client.CONNECTION_CONNECTED_STATUS
        self.fake.write_byte(client._address(
            self.ctx.slot_data["ram"]["addresses"]["current_challenge_index"]), 255)
        self.fake.write_u32(runtime.layout.mailbox + 8, popup.ACTIVE)
        client.CreateCommandProcessor._cmd_createpopupretry(SimpleNamespace(ctx=self.ctx))
        self.assertIs(runtime, self.ctx._popup_runtime)
        self.assertEqual(popup.ACTIVE, runtime.status(client.read_memory))


if __name__ == "__main__":
    unittest.main()
