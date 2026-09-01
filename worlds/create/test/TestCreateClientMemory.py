from __future__ import annotations

import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from .. import game_data
from ..client import client


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
        _challenge_palette_context=None,
        _challenge_palette_failure_logged=False,
        _contraption_patch_checked=False,
        _contraption_patch_applied=False,
        _chain_events_seen=set(),
        _chain_event_armed_contexts=set(),
        _chain_completion_context=None,
        _previous_chain_completion=None,
        _chain_context_ready_at=0.0,
        _hub_event_ready_at=0.0,
        _hub_challenge_spark_armed=False,
        _previous_hub_challenge_sparks=None,
        _spark_goal_access_logged=False,
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

    def test_object_registry_resolves_all_ids(self) -> None:
        records = client.resolve_object_records(self.ctx)

        self.assertEqual(client.OBJECT_RECORD_COUNT, len(records))
        self.assertEqual(self.records[13], records[13])

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

    def test_object_resync_is_queued_inside_challenge(self) -> None:
        with patch.object(client, "received_object_values", return_value={6}):
            client.sync_object_availability(self.ctx, challenge_active=True)

        self.assertTrue(self.ctx._object_resync_pending)
        self.assertEqual(0, self.fake.read_u32(self.records[6] + 0x2C))

        with patch.object(client, "received_object_values", return_value={6}):
            client.sync_object_availability(self.ctx, challenge_active=False)

        self.assertFalse(self.ctx._object_resync_pending)
        self.assertEqual(0, self.fake.read_u32(self.records[6] + 0x2C))
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
        self.fake.write_byte(current_challenge_address, 1)
        self.fake.write_u32(lead_address, root)
        self.fake.write_u32(root + client.OBJECT_LIST_OFFSET, list_container)
        self.fake.write_u32(list_container, entries)
        self.fake.write_u32(list_container + 0x04, 1)
        self.fake.write_u32(entries + 0x04, 0xDEADBEEF)

        with patch.object(client, "received_object_values", return_value=set()):
            client.filter_current_challenge_palette(self.ctx, challenge_active=True)

        self.assertEqual(0, self.fake.read_u32(entries + 0x04))
        self.assertEqual(0, self.fake.read_u32(entries))

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

    def test_create_chain_check_uses_chain_completion_without_popup_event(self) -> None:
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

    def test_hub_create_chain_ignores_stale_startup_completion(self) -> None:
        current_world_address = int(game_data.RAM_ADDRESSES["current_world_id"]["address"], 0)
        chain_completion_address = int(game_data.RAM_ADDRESSES["create_chain_completion"]["address"], 0)
        location_name = "Hub World Create Chain"
        self.ctx.slot_data["locations"][location_name] = {"id": 23456}
        self.fake.write_byte(current_world_address, 1)
        newly_checked: set[int] = set()

        self.fake.write_byte(chain_completion_address, 0)
        with patch.object(client.time, "monotonic", return_value=10.0):
            client.check_create_chain(self.ctx, newly_checked)
        self.fake.write_byte(chain_completion_address, 1)
        self.ctx._hub_event_ready_at = 60.0
        with patch.object(client.time, "monotonic", return_value=20.0):
            client.check_create_chain(self.ctx, newly_checked)

        self.assertEqual(set(), newly_checked)

    def test_hub_create_chain_sends_stable_completion_after_grace(self) -> None:
        current_world_address = int(game_data.RAM_ADDRESSES["current_world_id"]["address"], 0)
        chain_completion_address = int(game_data.RAM_ADDRESSES["create_chain_completion"]["address"], 0)
        location_name = "Hub World Create Chain"
        self.ctx.slot_data["locations"][location_name] = {"id": 23456}
        self.fake.write_byte(current_world_address, 1)
        self.fake.write_byte(chain_completion_address, 1)
        self.ctx._hub_event_ready_at = 20.0
        newly_checked: set[int] = set()

        with patch.object(client.time, "monotonic", return_value=10.0):
            client.check_create_chain(self.ctx, newly_checked)
        with patch.object(client.time, "monotonic", return_value=23.0):
            client.check_create_chain(self.ctx, newly_checked)

        self.assertEqual({23456}, newly_checked)

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

    def test_spark_requirement_can_unlock_goal_world_from_ap_spark_count(self) -> None:
        current_world_address = int(game_data.RAM_ADDRESSES["current_world_id"]["address"], 0)
        goal_world_access = int(game_data.CHALLENGE_RECORDS[6]["access"], 16)
        self.fake.write_byte(current_world_address, 1)
        self.fake.write_byte(goal_world_access, 0)

        with (
            patch.object(client, "received_world_keys", return_value=set()),
            patch.object(client, "received_spark_count", return_value=516),
        ):
            client.sync_world_access(self.ctx)

        self.assertEqual(1, self.fake.read_byte(goal_world_access))


if __name__ == "__main__":
    unittest.main()
