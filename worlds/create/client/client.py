from __future__ import annotations

import asyncio
import json
import sys
import time
import traceback
from argparse import Namespace
from pathlib import Path
from typing import Any

import ModuleUpdate
import Utils
from CommonClient import (
    ClientCommandProcessor,
    CommonContext,
    get_base_parser,
    gui_enabled,
    handle_url_arg,
    logger,
    server_loop,
)
from NetUtils import ClientStatus

from ..world_constants import GAME_ID_ADDRESS, GAME_NAME, ITEM_VICTORY, SPARK_ITEM_AMOUNTS
from ..world_constants import SUPPORTED_GAME_ID_LABEL, SUPPORTED_GAME_IDS
from ..world_constants import HUB_WORLD_KEY

ModuleUpdate.update()

CONNECTION_INITIAL_STATUS = "Dolphin connection has not been initiated."
CONNECTION_CONNECTED_STATUS = "Dolphin connected successfully."
CONNECTION_LOST_STATUS = "Dolphin connection was lost. Retrying..."
CONNECTION_REFUSED_GAME_STATUS = (
    f"Dolphin connected, but Create {SUPPORTED_GAME_ID_LABEL} is not running."
)
RAM_SETTLE_SECONDS = 10.0
CHAIN_CONTEXT_SETTLE_SECONDS = 2.0
WORLD_CONTEXT_SETTLE_SECONDS = 5.0
OBJECT_FREEZE_SLEEP_SECONDS = 0.02
DEFAULT_SYNC_SLEEP_SECONDS = 0.1
OBJECT_RECORD_COUNT = 262
OBJECT_LOCK_THRESHOLD = 0x7FFFFFFF
OBJECT_RESYNC_INTERVAL_SECONDS = 2.0
OBJECT_LIST_OFFSET = 0x04E4
CHALLENGE_OBJECT_ENTRY_STRIDE = 0x08


class CreateCommandProcessor(ClientCommandProcessor):
    ctx: "CreateContext"

    def _cmd_dolphin(self) -> None:
        """Display the current Dolphin connection status."""
        logger.info(f"Dolphin Status: {self.ctx.dolphin_status}")

    def _cmd_create(self) -> None:
        """Display Create client status."""
        logger.info(
            f"{len(self.ctx.locations_checked)} local checks, "
            f"{len(received_item_names(self.ctx))} received items, "
            f"Slot 3 armed: {self.ctx.save_slot_armed}."
        )


class CreateContext(CommonContext):
    command_processor = CreateCommandProcessor
    game = GAME_NAME
    items_handling = 0b111

    def __init__(
        self,
        server_address: str | None,
        password: str | None,
        patch_file: str | None = None,
    ) -> None:
        super().__init__(server_address, password)
        self.dolphin_status = CONNECTION_INITIAL_STATUS
        self.dolphin_sync_task: asyncio.Task[None] | None = None
        self.patch_data: dict[str, Any] = {}
        self.slot_data: dict[str, Any] = {}
        self.save_slot_armed = False
        self._save_slot_verified_once = False
        self._slot_guard_observed_this_session = False
        self._waiting_for_slot_logged = False
        self._slot_ready_at = 0.0
        self._slot_settle_logged = False
        self._location_context: tuple[int | None, str | None] | None = None
        self._location_context_ready_at = 0.0
        self._location_context_logged = False
        self._selected_object_freeze_context: tuple[str | None, int | None] | None = None
        self._selected_object_freeze_value: int | None = None
        self._object_records: dict[int, int] = {}
        self._object_resync_pending = True
        self._last_received_object_values: frozenset[int] = frozenset()
        self._last_object_resync_at = 0.0
        self._object_resolver_failure_logged = False
        self._challenge_palette_context: tuple[str | None, int | None] | None = None
        self._challenge_palette_failure_logged = False
        self._contraption_patch_checked = False
        self._contraption_patch_applied = False
        self._chain_events_seen: set[tuple[str | None, int]] = set()
        self._chain_completion_context: tuple[str | None, int | None] | None = None
        self._previous_chain_completion: int | None = None
        self._chain_context_ready_at = 0.0
        self._ram_ready_at = 0.0
        self._ram_settle_logged = False

        if patch_file:
            self.load_patch_file(patch_file)

    def load_patch_file(self, patch_file: str) -> None:
        path = Path(patch_file)
        with path.open("r", encoding="utf-8") as file:
            self.patch_data = json.load(file)
        self.slot_data = self.patch_data.get("slot_data", {})
        self.auth = self.slot_data.get("player_name") or self.auth
        logger.debug(f"Loaded {path.name}.")

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        if not self.auth:
            await self.get_username()
        await self.send_connect(game=self.game)

    def on_package(self, cmd: str, args: dict[str, Any]) -> None:
        if cmd == "Connected":
            self.slot_data = args["slot_data"]
            self.locations_checked = set()
            self.save_slot_armed = False
            self._slot_guard_observed_this_session = False
            self._waiting_for_slot_logged = False
            self._slot_ready_at = 0.0
            self._slot_settle_logged = False
            self._reset_ram_baselines()
            logger.debug("Connected to Archipelago as Create.")

    async def disconnect(self, allow_autoreconnect: bool = False) -> None:
        self.slot_data = self.patch_data.get("slot_data", {})
        self.save_slot_armed = False
        self._slot_guard_observed_this_session = False
        self._waiting_for_slot_logged = False
        self._slot_ready_at = 0.0
        self._slot_settle_logged = False
        self._reset_ram_baselines()
        await super().disconnect(allow_autoreconnect)

    def start_ram_settle(self) -> None:
        self._ram_ready_at = time.monotonic() + RAM_SETTLE_SECONDS
        self._ram_settle_logged = False
        self._reset_ram_baselines()

    def ram_is_settled(self) -> bool:
        remaining = self._ram_ready_at - time.monotonic()
        if remaining <= 0:
            return True
        if not self._ram_settle_logged:
            logger.info(f"Waiting {RAM_SETTLE_SECONDS:.0f}s for Create RAM to settle before reading or writing slot data.")
            self._ram_settle_logged = True
        return False

    def _reset_ram_baselines(self) -> None:
        self._reset_location_context()
        self._reset_selected_object_freeze()
        self._reset_object_runtime_state()
        self._chain_completion_context = None
        self._previous_chain_completion = None
        self._chain_context_ready_at = 0.0

    def _reset_location_context(self) -> None:
        self._location_context = None
        self._location_context_ready_at = 0.0
        self._location_context_logged = False

    def _reset_selected_object_freeze(self) -> None:
        self._selected_object_freeze_context = None
        self._selected_object_freeze_value = None

    def _reset_object_runtime_state(self) -> None:
        self._object_records = {}
        self._object_resync_pending = True
        self._last_received_object_values = frozenset()
        self._last_object_resync_at = 0.0
        self._object_resolver_failure_logged = False
        self._challenge_palette_context = None
        self._challenge_palette_failure_logged = False
        self._contraption_patch_checked = False
        self._contraption_patch_applied = False

    def start_slot_settle(self) -> None:
        self._slot_ready_at = time.monotonic() + RAM_SETTLE_SECONDS
        self._slot_settle_logged = False
        self._reset_ram_baselines()

    def slot_ram_is_settled(self) -> bool:
        remaining = self._slot_ready_at - time.monotonic()
        if remaining <= 0:
            return True
        if not self._slot_settle_logged:
            logger.info(f"Save Slot 3 observed. Waiting {RAM_SETTLE_SECONDS:.0f}s before AP RAM sync.")
            self._slot_settle_logged = True
        return False

    def make_gui(self):
        ui = super().make_gui()
        ui.base_title = "Archipelago Create Client"
        return ui


def _address(address_data: dict[str, Any]) -> int:
    return int(address_data["address"], 16)


def read_u8(address: int) -> int:
    import dolphin_memory_engine

    return dolphin_memory_engine.read_byte(address)


def read_u16_be(address: int) -> int:
    import dolphin_memory_engine

    return int.from_bytes(dolphin_memory_engine.read_bytes(address, 2), "big")


def read_u32_be(address: int) -> int:
    import dolphin_memory_engine

    return int.from_bytes(dolphin_memory_engine.read_bytes(address, 4), "big")


def write_u8(address: int, value: int) -> None:
    import dolphin_memory_engine

    dolphin_memory_engine.write_byte(address, value & 0xFF)


def write_u32_be(address: int, value: int) -> None:
    import dolphin_memory_engine

    dolphin_memory_engine.write_bytes(address, int(value).to_bytes(4, "big"))


def write_u8_if_changed(address: int, value: int) -> None:
    if read_u8(address) != value:
        write_u8(address, value)


def write_u16_be_if_changed(address: int, value: int) -> None:
    if read_u16_be(address) != value:
        import dolphin_memory_engine

        dolphin_memory_engine.write_bytes(address, int(value).to_bytes(2, "big"))


def write_u32_be_if_changed(address: int, value: int) -> None:
    if read_u32_be(address) != value:
        write_u32_be(address, value)


def item_name_from_network(ctx: CreateContext, item_id: int) -> str | None:
    try:
        return ctx.item_names.lookup_in_game(item_id, ctx.game)
    except Exception:
        return None


def received_item_names(ctx: CreateContext) -> list[str]:
    names: list[str] = []
    for network_item in ctx.items_received:
        item_name = item_name_from_network(ctx, network_item.item)
        if item_name:
            names.append(item_name)
    return names


def _mapping_lookup(mapping: dict[Any, Any], key: int) -> Any:
    return mapping.get(key, mapping.get(str(key)))


def _int_from_hexish(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    return int(str(value), 0)


def _plausible_pointer(value: int) -> bool:
    return 0x80000000 <= value <= 0x93FFFFFF and value % 4 == 0


def object_system_data(ctx: CreateContext) -> dict[str, Any]:
    return ctx.slot_data.get("ram", {}).get("object_system", {})


def find_first_object_node(ctx: CreateContext) -> int:
    object_system = object_system_data(ctx)
    registry_root = _int_from_hexish(object_system.get("registry_root"), 0x8066EA00)
    registry_key = _int_from_hexish(object_system.get("registry_key"), 0xA7390852)

    entry = read_u32_be(registry_root)
    for _ in range(512):
        if not entry:
            break
        if not _plausible_pointer(entry):
            raise RuntimeError(f"Object registry entry pointer is not plausible: 0x{entry:08X}")
        if read_u32_be(entry + 0x0C) == registry_key:
            node = read_u32_be(entry + 0x2C)
            if not _plausible_pointer(node):
                raise RuntimeError(f"Object node pointer is not plausible: 0x{node:08X}")
            return node
        entry = read_u32_be(entry + 0x28)
    raise RuntimeError("Object registry key was not found.")


def resolve_object_records(ctx: CreateContext) -> dict[int, int]:
    node = find_first_object_node(ctx)
    records: dict[int, int] = {}
    seen_nodes: set[int] = set()
    for object_id in range(OBJECT_RECORD_COUNT):
        if not node:
            raise RuntimeError(f"Object list ended before object ID {object_id}.")
        if node in seen_nodes:
            raise RuntimeError(f"Object list looped at node 0x{node:08X}.")
        if not _plausible_pointer(node):
            raise RuntimeError(f"Object node pointer is not plausible: 0x{node:08X}")
        seen_nodes.add(node)
        record = read_u32_be(node + 0x10)
        if not _plausible_pointer(record):
            raise RuntimeError(f"Availability record for object ID {object_id} is not plausible: 0x{record:08X}")
        records[object_id] = record
        node = read_u32_be(node + 0x14)
    return records


def object_records(ctx: CreateContext) -> dict[int, int] | None:
    if len(ctx._object_records) == OBJECT_RECORD_COUNT:
        return ctx._object_records
    try:
        ctx._object_records = resolve_object_records(ctx)
        ctx._object_resolver_failure_logged = False
        logger.info(f"Resolved {len(ctx._object_records)} Create Object availability records.")
    except Exception as error:
        ctx._object_records = {}
        if not ctx._object_resolver_failure_logged:
            logger.warning(f"Could not resolve Create Object availability records; Object RAM resync is paused: {error}")
            ctx._object_resolver_failure_logged = True
        return None
    return ctx._object_records


def active_challenge_raw(ctx: CreateContext) -> int:
    return current_challenge_raw(ctx)


def in_challenge(raw_challenge: int | None = None) -> bool:
    if raw_challenge is None:
        return False
    return 0 <= raw_challenge <= 10


def sync_save_slot_guard(ctx: CreateContext) -> None:
    if not ctx.slot_data:
        return
    if ctx._save_slot_verified_once:
        if not ctx.save_slot_armed:
            logger.info("Save Slot 3 was verified earlier. Skipping guard read for this reconnect.")
        ctx.save_slot_armed = True
        return

    guard = _address(ctx.slot_data["ram"]["addresses"]["save_slot_guard_primary"])
    try:
        value = read_u8(guard)
    except Exception:
        ctx.save_slot_armed = False
        return

    if value == 2:
        if not ctx._slot_guard_observed_this_session:
            ctx._slot_guard_observed_this_session = True
            ctx.start_slot_settle()
        if not ctx.slot_ram_is_settled():
            ctx.save_slot_armed = False
            return
        if not ctx.save_slot_armed:
            logger.info("Save Slot 3 RAM settled. RAM writes and location sending are now enabled.")
        ctx.save_slot_armed = True
        ctx._save_slot_verified_once = True
        return

    if value == 0xFF and ctx._slot_guard_observed_this_session:
        ctx.save_slot_armed = ctx.slot_ram_is_settled()
        return

    if ctx.save_slot_armed:
        logger.info("Save Slot 3 guard no longer matches. RAM writes and location sending are paused.")
    elif not ctx._waiting_for_slot_logged:
        logger.info("Waiting for Save Slot 3 guard before sending checks or writing RAM.")
        ctx._waiting_for_slot_logged = True
    ctx.save_slot_armed = False
    ctx._slot_guard_observed_this_session = False
    ctx._slot_ready_at = 0.0
    ctx._slot_settle_logged = False


def current_world_key(ctx: CreateContext) -> str | None:
    world_id = current_world_id(ctx)
    if world_id == 1:
        return None
    confirmed = ctx.slot_data["ram"]["confirmed_current_world_ids"]
    world_key = _mapping_lookup(confirmed, world_id)
    if world_key:
        return world_key
    return _mapping_lookup(ctx.slot_data["ram"]["expected_current_world_ids"], world_id)


def current_world_id(ctx: CreateContext) -> int:
    return read_u8(_address(ctx.slot_data["ram"]["addresses"]["current_world_id"]))


def current_challenge_index(ctx: CreateContext) -> int | None:
    value = current_challenge_raw(ctx)
    if 0 <= value <= 9:
        return value + 1
    if value == 10:
        return 1
    return None


def current_challenge_raw(ctx: CreateContext) -> int:
    value = read_u8(_address(ctx.slot_data["ram"]["addresses"]["current_challenge_index"]))
    return value


def checked_location(ctx: CreateContext, location_name: str, newly_checked: set[int]) -> None:
    location = ctx.slot_data.get("locations", {}).get(location_name)
    if not location:
        return
    location_id = location.get("id")
    if location_id and location_id not in ctx.locations_checked:
        ctx.locations_checked.add(location_id)
        newly_checked.add(location_id)
        logger.debug(f"Checked: {location_name}")


def check_challenge_sparks(ctx: CreateContext, newly_checked: set[int]) -> None:
    if current_world_id(ctx) == 1 and current_challenge_raw(ctx) == 10:
        earned = read_u8(_address(ctx.slot_data["ram"]["addresses"]["current_challenge_sparks"]))
        if earned > 0:
            checked_location(ctx, "Hub World Challenge 1 - Reward", newly_checked)
        return

    world_key = current_world_key(ctx)
    if not world_key:
        return
    records = ctx.slot_data["ram"]["challenge_records"]
    for record in records:
        challenge = int(record["challenge"])
        earned = min(read_u8(int(record["earned"], 16)), 6)
        if earned <= 0:
            continue
        challenge_key = f"{world_key}:{challenge}"
        challenge_data = ctx.slot_data["challenges"].get(challenge_key)
        if not challenge_data:
            continue
        max_reward = int(challenge_data["spark_reward"])
        for spark in range(1, min(earned, max_reward) + 1):
            checked_location(
                ctx,
                f"{challenge_data['world_name']} Challenge {challenge:02d} Spark {spark}",
                newly_checked,
            )


def check_create_chain(ctx: CreateContext, newly_checked: set[int]) -> None:
    world_id = current_world_id(ctx)
    if world_id != 1 and not ctx.slot_data["options"].get("create_chain_checks", True):
        return
    world_key = current_world_key(ctx)
    chain_index = None
    if world_id != 1 and world_key is not None:
        chain_index = read_u8(_address(ctx.slot_data["ram"]["addresses"]["create_chain_index"]))

    completion_flag = read_u8(_address(ctx.slot_data["ram"]["addresses"]["create_chain_completion"]))
    context_key = (world_key if world_id != 1 else None, chain_index)
    if ctx._chain_completion_context != context_key:
        ctx._chain_completion_context = context_key
        ctx._previous_chain_completion = completion_flag
        ctx._chain_context_ready_at = time.monotonic() + CHAIN_CONTEXT_SETTLE_SECONDS
        return
    if time.monotonic() < ctx._chain_context_ready_at:
        ctx._previous_chain_completion = completion_flag
        return

    previous_completion = ctx._previous_chain_completion
    ctx._previous_chain_completion = completion_flag
    if (
        previous_completion is None
        or previous_completion == 1
        or completion_flag != 1
    ):
        return

    if world_id == 1:
        event_key = (None, 1)
        if event_key not in ctx._chain_events_seen:
            checked_location(ctx, "Hub World Create Chain", newly_checked)
            ctx._chain_events_seen.add(event_key)
    elif world_key is not None:
        chain = max(1, min(5, (chain_index or 0) + 1))
        event_key = (world_key, chain)
        if event_key not in ctx._chain_events_seen:
            world_name = ctx.slot_data["worlds"][world_key]["name"]
            checked_location(ctx, f"{world_name} Create Chain {chain}", newly_checked)
            ctx._chain_events_seen.add(event_key)


def location_context_is_settled(ctx: CreateContext) -> bool:
    world_id = current_world_id(ctx)
    context = (world_id, current_world_key(ctx))
    if ctx._location_context != context:
        ctx._location_context = context
        ctx._location_context_ready_at = time.monotonic() + WORLD_CONTEXT_SETTLE_SECONDS
        ctx._location_context_logged = False
        ctx._chain_completion_context = None
        ctx._previous_chain_completion = None
        ctx._chain_context_ready_at = 0.0
        return False

    remaining = ctx._location_context_ready_at - time.monotonic()
    if remaining <= 0:
        return True
    if not ctx._location_context_logged:
        logger.info(f"Waiting {WORLD_CONTEXT_SETTLE_SECONDS:.0f}s after world load before sending Create checks.")
        ctx._location_context_logged = True
    return False


async def check_locations(ctx: CreateContext) -> None:
    if not ctx.slot_data or not ctx.save_slot_armed:
        return
    newly_checked: set[int] = set()
    try:
        if not location_context_is_settled(ctx):
            return
        check_challenge_sparks(ctx, newly_checked)
        check_create_chain(ctx, newly_checked)
    except Exception:
        logger.debug("Failed while checking Create locations.", exc_info=True)
    if newly_checked and ctx.slot is not None:
        await ctx.send_msgs([{"cmd": "LocationChecks", "locations": list(newly_checked)}])


def received_world_keys(ctx: CreateContext) -> set[str]:
    received = set(received_item_names(ctx))
    return {
        world_key
        for world_key, data in ctx.slot_data.get("worlds", {}).items()
        if data["access_item"] in received
    }


def received_object_values(ctx: CreateContext) -> set[int]:
    received = set(received_item_names(ctx))
    return {
        int(data["global_value"])
        for item_name, data in ctx.slot_data.get("objects", {}).items()
        if item_name in received
    }


def received_spark_count(ctx: CreateContext) -> int:
    return sum(SPARK_ITEM_AMOUNTS.get(item_name, 0) for item_name in received_item_names(ctx))


def apply_owned_object_record(record: int) -> None:
    write_u32_be_if_changed(record + 0x0C, 0)
    write_u32_be_if_changed(record + 0x14, 0)
    write_u32_be_if_changed(record + 0x2C, 0)


def apply_unowned_object_record(record: int) -> None:
    write_u32_be_if_changed(record + 0x2C, OBJECT_LOCK_THRESHOLD)


def sync_object_availability(ctx: CreateContext, challenge_active: bool) -> None:
    owned_values = frozenset(received_object_values(ctx))
    if owned_values != ctx._last_received_object_values:
        ctx._last_received_object_values = owned_values
        ctx._object_resync_pending = True

    if challenge_active:
        return

    now = time.monotonic()
    if (
        not ctx._object_resync_pending
        and now - ctx._last_object_resync_at < OBJECT_RESYNC_INTERVAL_SECONDS
    ):
        return

    records = object_records(ctx)
    if not records:
        return

    for object_data in ctx.slot_data.get("objects", {}).values():
        object_id = int(object_data["global_value"])
        record = records.get(object_id)
        if not record:
            continue
        if object_id in owned_values:
            apply_owned_object_record(record)
        else:
            apply_unowned_object_record(record)

    ctx._object_resync_pending = False
    ctx._last_object_resync_at = now


def current_challenge_context(ctx: CreateContext) -> tuple[str | None, int | None, int]:
    raw_challenge = current_challenge_raw(ctx)
    if current_world_id(ctx) == 1 and raw_challenge == 10:
        return HUB_WORLD_KEY, 1, raw_challenge
    return current_world_key(ctx), current_challenge_index(ctx), raw_challenge


def hub_create_chain_location_id(ctx: CreateContext) -> int | None:
    location = ctx.slot_data.get("locations", {}).get("Hub World Create Chain")
    if not location:
        return None
    return location.get("id")


def hub_create_chain_done(ctx: CreateContext) -> bool:
    location_id = hub_create_chain_location_id(ctx)
    return bool(
        location_id
        and (location_id in ctx.locations_checked or location_id in ctx.checked_locations)
    )


def sync_world_access(ctx: CreateContext) -> None:
    if not ctx.save_slot_armed:
        return
    current_world_id = read_u8(_address(ctx.slot_data["ram"]["addresses"]["current_world_id"]))
    if current_world_id != 1:
        return

    owned_worlds = received_world_keys(ctx)
    records = ctx.slot_data["ram"]["challenge_records"]
    for world_key, world_data in ctx.slot_data.get("worlds", {}).items():
        unlocked = 1 if world_key in owned_worlds else 0
        if world_key == ctx.slot_data.get("starting_world") and not hub_create_chain_done(ctx):
            unlocked = 0
        if not world_data.get("included", True):
            continue
        hub_index = int(ctx.slot_data["worlds"][world_key]["hub_index"])
        if hub_index < 10:
            write_u8_if_changed(int(records[hub_index]["access"], 16), unlocked)
        else:
            world_name = world_data["name"]
            for raw_address in ctx.slot_data["ram"]["ii_world_flags"][world_name]:
                write_u8_if_changed(int(raw_address, 16), unlocked)


def sync_total_sparks(ctx: CreateContext) -> None:
    return


def _read_challenge_object_list_candidate(container: int) -> tuple[int, int] | None:
    if not _plausible_pointer(container):
        return None
    entries = read_u32_be(container)
    count = read_u32_be(container + 0x04)
    if not _plausible_pointer(entries) or count > 64:
        return None
    return entries, count


def resolve_current_challenge_object_list(expected_count: int, ctx: CreateContext) -> tuple[int, int] | None:
    object_system = object_system_data(ctx)
    lead_address = _int_from_hexish(object_system.get("challenge_object_root_lead"), 0x808D1CD4)
    lead = read_u32_be(lead_address)
    candidates: list[int] = []
    if _plausible_pointer(lead):
        candidates.append(lead)
        try:
            candidates.append(read_u32_be(lead + OBJECT_LIST_OFFSET))
        except Exception:
            pass

    for candidate in candidates:
        resolved = _read_challenge_object_list_candidate(candidate)
        if resolved is None:
            continue
        entries, count = resolved
        if count >= expected_count:
            return entries, count
    return None


def filter_current_challenge_palette(ctx: CreateContext, challenge_active: bool) -> bool:
    if not challenge_active:
        ctx._challenge_palette_context = None
        ctx._challenge_palette_failure_logged = False
        return False

    world_key, challenge, _ = current_challenge_context(ctx)
    context = (world_key, challenge)
    challenge_data = ctx.slot_data["challenges"].get(f"{world_key}:{challenge}") if world_key and challenge else None
    if not challenge_data or challenge_data["type"] != "local":
        ctx._challenge_palette_context = context
        return False

    objects = challenge_data["objects"]
    resolved = resolve_current_challenge_object_list(len(objects), ctx)
    if resolved is None:
        if ctx._challenge_palette_context != context or not ctx._challenge_palette_failure_logged:
            logger.debug("Could not resolve the current Create challenge Object palette.", exc_info=False)
            ctx._challenge_palette_failure_logged = True
        ctx._challenge_palette_context = context
        return False

    entries, count = resolved
    owned_values = received_object_values(ctx)
    for obj in objects:
        selected_value = int(obj["selected_value"])
        global_value = int(obj["global_value"])
        if selected_value >= count or global_value in owned_values:
            continue
        write_u32_be_if_changed(entries + selected_value * CHALLENGE_OBJECT_ENTRY_STRIDE + 0x04, 0)

    ctx._challenge_palette_context = context
    ctx._challenge_palette_failure_logged = False
    return True


def ensure_contraption_patch(ctx: CreateContext, challenge_active: bool) -> None:
    if challenge_active and not ctx._contraption_patch_applied:
        return
    object_system = object_system_data(ctx)
    patch_data = object_system.get("contraption_patch")
    if not patch_data:
        return
    address = _int_from_hexish(patch_data.get("address"))
    original = _int_from_hexish(patch_data.get("original"))
    patched = _int_from_hexish(patch_data.get("patched"))
    try:
        current = read_u32_be(address)
    except Exception:
        return
    if current == patched:
        ctx._contraption_patch_checked = True
        ctx._contraption_patch_applied = True
        return
    if current != original:
        if not ctx._contraption_patch_checked:
            logger.warning(
                f"Create Contraption patch skipped: expected 0x{original:08X} "
                f"at 0x{address:08X}, found 0x{current:08X}."
            )
        ctx._contraption_patch_checked = True
        return
    write_u32_be(address, patched)
    ctx._contraption_patch_checked = True
    ctx._contraption_patch_applied = True
    logger.info("Applied Create Contraption-o-matic availability patch.")


def enforce_selected_object(ctx: CreateContext) -> bool:
    if not ctx.save_slot_armed:
        ctx._reset_selected_object_freeze()
        return False
    selected_address = _address(ctx.slot_data["ram"]["addresses"]["selected_object"])
    selected = read_u32_be(selected_address)
    owned_values = received_object_values(ctx)
    freeze_active = False

    def force_selected_value(context: tuple[str | None, int | None], value: int) -> bool:
        if (
            ctx._selected_object_freeze_context != context
            or ctx._selected_object_freeze_value != value
        ):
            logger.debug(f"Freezing selected object value at {value}.")
        ctx._selected_object_freeze_context = context
        ctx._selected_object_freeze_value = value
        write_u32_be_if_changed(selected_address, value)
        return True

    def block_unowned_global_selection(context: tuple[str | None, int | None]) -> bool:
        unlockable_values = {
            int(data["global_value"])
            for data in ctx.slot_data.get("objects", {}).values()
        }
        if selected in unlockable_values and selected not in owned_values:
            logger.debug(f"Blocking unowned global object value {selected}.")
            return force_selected_value(context, 0)
        ctx._reset_selected_object_freeze()
        return False

    if current_world_id(ctx) == 1 and current_challenge_raw(ctx) == 10:
        world_key = HUB_WORLD_KEY
    else:
        world_key = current_world_key(ctx)
    challenge = current_challenge_index(ctx)
    context = (world_key, challenge)
    if ctx._selected_object_freeze_context != context:
        ctx._reset_selected_object_freeze()
    if not world_key or not challenge:
        return block_unowned_global_selection(context)

    challenge_data = ctx.slot_data["challenges"].get(f"{world_key}:{challenge}")
    if not challenge_data:
        return block_unowned_global_selection(context)

    if challenge_data["type"] == "local":
        local_objects = {
            int(obj["selected_value"]): obj
            for obj in challenge_data["objects"]
        }
        selected_object = local_objects.get(selected)
        if selected_object and int(selected_object["global_value"]) in owned_values:
            ctx._reset_selected_object_freeze()
            return False
        block_value = int(challenge_data.get("block_value") or (len(local_objects) + 1))
        if selected != block_value:
            logger.debug(
                f"Blocking unowned local object value {selected} "
                f"in {challenge_data['world_name']} Challenge {challenge:02d}."
            )
        freeze_active = force_selected_value(context, block_value)
        return freeze_active

    return block_unowned_global_selection(context)


def process_victory(ctx: CreateContext) -> None:
    if ctx.finished_game:
        return
    required_sparks = int(ctx.slot_data.get("required_sparks", 0))
    if ITEM_VICTORY in received_item_names(ctx) and received_spark_count(ctx) >= required_sparks:
        Utils.async_start(ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}]))
        ctx.finished_game = True


async def dolphin_sync_task(ctx: CreateContext) -> None:
    import dolphin_memory_engine

    logger.info("Starting Dolphin connector. Use /dolphin for status information.")
    sleep_time = 0.0
    while not ctx.exit_event.is_set():
        if sleep_time:
            try:
                await asyncio.wait_for(ctx.watcher_event.wait(), sleep_time)
            except asyncio.TimeoutError:
                pass
            sleep_time = 0.0
        ctx.watcher_event.clear()

        try:
            if dolphin_memory_engine.is_hooked() and ctx.dolphin_status == CONNECTION_CONNECTED_STATUS:
                if dolphin_memory_engine.read_bytes(GAME_ID_ADDRESS, 6) not in SUPPORTED_GAME_IDS:
                    dolphin_memory_engine.un_hook()
                    ctx.dolphin_status = CONNECTION_LOST_STATUS
                    ctx.start_ram_settle()
                    sleep_time = 2
                    continue
                object_freeze_active = False
                if ctx.slot_data:
                    if not ctx.ram_is_settled():
                        sleep_time = 0.5
                        continue
                    sync_save_slot_guard(ctx)
                    if not ctx.save_slot_armed:
                        sleep_time = 0.5
                        continue
                    raw_challenge = current_challenge_raw(ctx)
                    challenge_active = in_challenge(raw_challenge)
                    sync_world_access(ctx)
                    sync_total_sparks(ctx)
                    local_challenge_runtime_active = filter_current_challenge_palette(ctx, challenge_active)
                    sync_object_availability(ctx, local_challenge_runtime_active)
                    ensure_contraption_patch(ctx, local_challenge_runtime_active)
                    object_freeze_active = enforce_selected_object(ctx)
                    await check_locations(ctx)
                    process_victory(ctx)
                sleep_time = OBJECT_FREEZE_SLEEP_SECONDS if object_freeze_active else DEFAULT_SYNC_SLEEP_SECONDS
                continue

            if ctx.dolphin_status == CONNECTION_CONNECTED_STATUS:
                logger.info("Connection to Dolphin lost, reconnecting...")
            ctx.dolphin_status = CONNECTION_LOST_STATUS
            logger.info("Attempting to connect to Dolphin...")
            dolphin_memory_engine.hook()
            if not dolphin_memory_engine.is_hooked():
                sleep_time = 5
                continue

            if dolphin_memory_engine.read_bytes(GAME_ID_ADDRESS, 6) not in SUPPORTED_GAME_IDS:
                logger.info(CONNECTION_REFUSED_GAME_STATUS)
                ctx.dolphin_status = CONNECTION_REFUSED_GAME_STATUS
                dolphin_memory_engine.un_hook()
                sleep_time = 5
                continue

            ctx.dolphin_status = CONNECTION_CONNECTED_STATUS
            logger.info(CONNECTION_CONNECTED_STATUS)
            ctx.start_ram_settle()
        except Exception:
            dolphin_memory_engine.un_hook()
            ctx.dolphin_status = CONNECTION_LOST_STATUS
            ctx.start_ram_settle()
            logger.error(traceback.format_exc())
            sleep_time = 5


async def main(args: Namespace) -> None:
    ctx = CreateContext(args.connect, args.password, args.patch_file)
    ctx.auth = args.name or ctx.auth
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="ServerLoop")

    if gui_enabled and not getattr(args, "nogui", False):
        ctx.run_gui()
    ctx.run_cli()

    ctx.dolphin_sync_task = asyncio.create_task(dolphin_sync_task(ctx), name="DolphinSync")
    await ctx.exit_event.wait()
    ctx.watcher_event.set()
    await ctx.shutdown()
    if ctx.dolphin_sync_task:
        await ctx.dolphin_sync_task


def launch(*args: str) -> None:
    parser = get_base_parser(description="Create Archipelago Client")
    parser.add_argument("--name", default=None, help="Slot Name to connect as.")
    parser.add_argument("url", nargs="?", help="Archipelago connection url or .apcreate output file")
    parsed_args = parser.parse_args(args)
    if parsed_args.url and str(parsed_args.url).endswith(".apcreate"):
        parsed_args.patch_file = parsed_args.url
        parsed_args.url = None
    else:
        parsed_args.patch_file = None
        parsed_args = handle_url_arg(parsed_args, parser=parser)
    Utils.init_logging("CreateClient", exception_logger="Client")
    asyncio.run(main(parsed_args))


if __name__ == "__main__":
    launch(*sys.argv[1:])
