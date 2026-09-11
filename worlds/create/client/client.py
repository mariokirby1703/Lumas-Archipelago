from __future__ import annotations

import asyncio
import json
import sys
import time
import traceback
from argparse import Namespace
from collections import deque
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
from .popup_runtime import PopupRuntime, IDLE, ACTIVE, ERROR, MODAL_LAYER
from .popup_runtime import CACHE_HELPER_NAME, cache_flush_gecko_code

ModuleUpdate.update()

CONNECTION_INITIAL_STATUS = "Dolphin connection has not been initiated."
CONNECTION_CONNECTED_STATUS = "Dolphin connected successfully."
CONNECTION_LOST_STATUS = "Dolphin connection was lost. Retrying..."
CONNECTION_REFUSED_GAME_STATUS = (
    f"Dolphin connected, but Create {SUPPORTED_GAME_ID_LABEL} is not running."
)
RAM_SETTLE_SECONDS = 10.0
SLOT_SETTLE_SECONDS = 5.0
CHAIN_CONTEXT_SETTLE_SECONDS = 2.0
WORLD_CONTEXT_SETTLE_SECONDS = 5.0
OBJECT_FREEZE_SLEEP_SECONDS = 0.02
DEFAULT_SYNC_SLEEP_SECONDS = 0.1
OBJECT_RECORD_COUNT = 262
OBJECT_LOCK_THRESHOLD = 0x7FFFFFFF
OBJECT_RESYNC_INTERVAL_SECONDS = 2.0
OBJECT_RESOLVER_RETRY_SECONDS = 1.0
OBJECT_MEM2_REHOOK_LIMIT = 3
OBJECT_RESYNC_AFTER_CHAIN_DELAY_SECONDS = 5.0
HUB_EVENT_GRACE_SECONDS = 30.0
OBJECT_LIST_OFFSET = 0x04E4
CHALLENGE_OBJECT_ENTRY_STRIDE = 0x08

class CreateCommandProcessor(ClientCommandProcessor):
    ctx: "CreateContext"

    def _cmd_createpopup(self, object_id: str = "") -> None:
        """Queue a vanilla Object Unlocked popup: /createpopup <0..261>."""
        try:
            value = int(object_id)
        except ValueError:
            logger.warning("Usage: /createpopup <object_id>, integer 0..261.")
            return
        if not 0 <= value < OBJECT_RECORD_COUNT or not any(
            int(data["global_value"]) == value for data in self.ctx.slot_data.get("objects", {}).values()
        ):
            logger.warning("Object ID must be an unlockable Object in this slot (0..261).")
            return
        self.ctx._object_popup_queue.append(value)
        logger.info("Queued Object popup: %s (ID %d).", popup_object_name(self.ctx, value), value)
        if self.ctx._popup_runtime.failure:
            logger.warning("Popup display is blocked: %s. The Object remains queued.",
                           self.ctx._popup_runtime.failure)

    def _cmd_createpopupretry(self) -> None:
        """Retry the popup hook for 120 seconds without clearing the receipt queue."""
        ctx = self.ctx
        if (ctx.dolphin_status != CONNECTION_CONNECTED_STATUS or not ctx.save_slot_armed
                or not ctx.ram_is_settled() or not ctx.slot_ram_is_settled()):
            logger.warning("Popup retry requires Dolphin and settled Save Slot 3 RAM.")
            return
        if in_challenge(current_challenge_raw(ctx)):
            logger.warning("Leave the challenge before retrying the popup hook.")
            return
        state = ctx._popup_runtime.snapshot(read_memory)
        if state["status"] == ACTIVE or state["active"] or state["popup_pointer"]:
            logger.warning("Close the active popup normally before retrying.")
            return
        ctx._popup_runtime.uninstall(read_memory, write_memory)
        ctx._popup_runtime = PopupRuntime(probe_timeout=120.0)
        ctx._popup_runtime_ready = False
        ctx._popup_last_status = None
        logger.info("Popup diagnostic retry requested (120 seconds). Queue retained. "
                    "Keep Dolphin running in the Hub/world; use /createpopupstatus for diagnostics. "
                    "This command does not clear Dolphin's instruction cache.")

    def _cmd_createpopupcache(self) -> None:
        """Print the Dolphin Gecko helper needed to invalidate popup instruction caches."""
        logger.info("In Dolphin, enable cheats and add/enable this code under CREATE > Properties > "
                    "Gecko Codes. Restart the game after enabling it. Name: %s\n%s",
                    CACHE_HELPER_NAME, cache_flush_gecko_code())

    def _cmd_createpopupstatus(self) -> None:
        """Display popup patch, mailbox, modal layer and queue diagnostics."""
        runtime = self.ctx._popup_runtime
        logger.info("Popup installed=%s ready=%s failure=%s queue=%d", runtime.installed,
                    runtime.ready, runtime.failure, len(self.ctx._object_popup_queue))
        if self.ctx.dolphin_status == CONNECTION_CONNECTED_STATUS:
            try:
                logger.info("Popup hook diagnostics: %s", runtime.diagnostics(read_memory))
                logger.info("Popup mailbox=%s modal=%d", runtime.snapshot(read_memory), read_u32_be(MODAL_LAYER))
            except Exception as error:
                logger.warning("Popup status unavailable: %s", error)

    def _cmd_dolphin(self) -> None:
        """Display the current Dolphin connection status."""
        logger.info(f"Dolphin Status: {self.ctx.dolphin_status}")

    def _cmd_create(self) -> None:
        """Display Create client status."""
        logger.info(
            f"{len(self.ctx.locations_checked)} local checks, "
            f"{len(received_item_names(self.ctx))} received items, "
            f"{received_spark_count(self.ctx)} AP Sparks, "
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
        self._popup_runtime = PopupRuntime()
        self._popup_runtime_ready = False
        self._popup_item_cursor = 0
        self._popup_accept_new_items = False
        self._object_popup_queue: deque[int] = deque()
        self._popup_inflight: tuple[int, int] | None = None
        self._popup_last_status: int | None = None
        self._popup_delay_logged = False
        self._slot_guard_observed_this_session = False
        self._waiting_for_slot_logged = False
        self._slot_connected_logged = False
        self._slot_ready_at = 0.0
        self._slot_settle_logged = False
        self._location_context: tuple[int | None, str | None] | None = None
        self._location_context_ready_at = 0.0
        self._location_context_logged = False
        self._selected_object_freeze_context: tuple[str | None, int | None] | None = None
        self._selected_object_freeze_value: int | None = None
        self._object_records: dict[int, int] = {}
        self._object_resync_pending = True
        self._object_resync_blocked_until = 0.0
        self._last_received_object_values: frozenset[int] = frozenset()
        self._last_object_resync_at = 0.0
        self._object_resolver_failure_logged = False
        self._object_resolver_retry_at = 0.0
        self._object_resolver_trace: dict[str, int] = {}
        self._object_mem2_rehook_requested = False
        self._object_mem2_rehook_attempts = 0
        self._challenge_palette_context: tuple[str | None, int | None] | None = None
        self._challenge_palette_keys: dict[int, int] = {}
        self._challenge_palette_failure_logged = False
        self._contraption_patch_checked = False
        self._contraption_patch_applied = False
        self._chain_events_seen: set[tuple[str | None, int]] = set()
        self._chain_event_armed_contexts: set[tuple[str | None, int | None]] = set()
        self._chain_completion_context: tuple[str | None, int | None] | None = None
        self._previous_chain_completion: int | None = None
        self._hub_event_ready_at = 0.0
        self._hub_challenge_spark_armed = False
        self._previous_hub_challenge_sparks: int | None = None
        self._hub_chain_part_sequence: int | None = None
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
            self._slot_connected_logged = False
            self._slot_ready_at = 0.0
            self._slot_settle_logged = False
            self._reset_ram_baselines()
            logger.debug("Connected to Archipelago as Create.")

    async def disconnect(self, allow_autoreconnect: bool = False) -> None:
        self.slot_data = self.patch_data.get("slot_data", {})
        self.save_slot_armed = False
        self._slot_guard_observed_this_session = False
        self._waiting_for_slot_logged = False
        self._slot_connected_logged = False
        self._slot_ready_at = 0.0
        self._slot_settle_logged = False
        self._reset_ram_baselines()
        await super().disconnect(allow_autoreconnect)

    def start_ram_settle(self) -> None:
        self.save_slot_armed = False
        self._slot_guard_observed_this_session = False
        self._slot_ready_at = 0.0
        self._slot_settle_logged = False
        self._slot_connected_logged = False
        reset_mem2_fallback()
        self._ram_ready_at = time.monotonic() + RAM_SETTLE_SECONDS
        self._ram_settle_logged = False
        self._reset_ram_baselines()

    def ram_is_settled(self) -> bool:
        remaining = self._ram_ready_at - time.monotonic()
        if remaining <= 0:
            return True
        return False

    def _reset_ram_baselines(self) -> None:
        self._reset_popup_state()
        self._reset_location_context()
        self._reset_selected_object_freeze()
        self._reset_object_runtime_state()
        self._chain_completion_context = None
        self._previous_chain_completion = None
        self._chain_context_ready_at = 0.0

    def _reset_popup_state(self) -> None:
        if self.dolphin_status == CONNECTION_CONNECTED_STATUS:
            self._popup_runtime.uninstall(read_memory, write_memory)
        self._popup_runtime = PopupRuntime()
        self._popup_runtime_ready = False
        self._popup_item_cursor = 0
        self._popup_accept_new_items = False
        self._object_popup_queue.clear()
        self._popup_inflight = None
        self._popup_last_status = None
        self._popup_delay_logged = False

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
        self._object_resync_blocked_until = 0.0
        self._last_received_object_values = frozenset()
        self._last_object_resync_at = 0.0
        self._object_resolver_failure_logged = False
        self._object_resolver_retry_at = 0.0
        self._object_resolver_trace = {}
        self._challenge_palette_context = None
        self._challenge_palette_keys = {}
        self._challenge_palette_failure_logged = False
        self._contraption_patch_checked = False
        self._contraption_patch_applied = False
        self._chain_event_armed_contexts = set()
        self._hub_event_ready_at = 0.0
        self._hub_challenge_spark_armed = False
        self._previous_hub_challenge_sparks = None
        self._hub_chain_part_sequence = None

    def start_slot_settle(self) -> None:
        self._slot_ready_at = time.monotonic() + SLOT_SETTLE_SECONDS
        self._slot_settle_logged = False
        self._reset_ram_baselines()

    def slot_ram_is_settled(self) -> bool:
        remaining = self._slot_ready_at - time.monotonic()
        if remaining <= 0:
            return True
        return False

    def make_gui(self):
        ui = super().make_gui()
        ui.base_title = "Archipelago Create Client"
        return ui


def _address(address_data: dict[str, Any]) -> int:
    return int(address_data["address"], 16)


_mem2_fallback = None
_mem2_fallback_retry_at = 0.0


def reset_mem2_fallback() -> None:
    global _mem2_fallback, _mem2_fallback_retry_at
    if _mem2_fallback is not None:
        _mem2_fallback.close()
    _mem2_fallback = None
    _mem2_fallback_retry_at = 0.0


def read_memory(address: int, size: int) -> bytes:
    import dolphin_memory_engine

    global _mem2_fallback, _mem2_fallback_retry_at
    mem2 = 0x90000000 <= address < address + size <= 0x94000000
    if mem2 and _mem2_fallback is not None:
        return _mem2_fallback.read(address, size)
    try:
        return dolphin_memory_engine.read_bytes(address, size)
    except RuntimeError:
        if not mem2 or sys.platform != "win32" or time.monotonic() < _mem2_fallback_retry_at:
            raise
        _mem2_fallback_retry_at = time.monotonic() + OBJECT_RESOLVER_RETRY_SECONDS
        from .windows_mem2 import WindowsMEM2

        fallback = WindowsMEM2(dolphin_memory_engine)
        try:
            result = fallback.read(address, size)
        except Exception:
            fallback.close()
            raise
        _mem2_fallback = fallback
        logger.info("Create MEM2 connected through verified Windows RAM mapping.")
        return result


def write_memory(address: int, data: bytes) -> None:
    import dolphin_memory_engine

    if _mem2_fallback is not None and 0x90000000 <= address < address + len(data) <= 0x94000000:
        _mem2_fallback.write(address, data)
    else:
        dolphin_memory_engine.write_bytes(address, data)


def read_u8(address: int) -> int:
    return read_memory(address, 1)[0]


def read_u16_be(address: int) -> int:
    return int.from_bytes(read_memory(address, 2), "big")


def read_u32_be(address: int) -> int:
    return int.from_bytes(read_memory(address, 4), "big")


def write_u8(address: int, value: int) -> None:
    write_memory(address, bytes([value & 0xFF]))


def write_u32_be(address: int, value: int) -> None:
    write_memory(address, int(value).to_bytes(4, "big"))


def write_u8_if_changed(address: int, value: int) -> None:
    if read_u8(address) != value:
        write_u8(address, value)


def write_u16_be_if_changed(address: int, value: int) -> None:
    if read_u16_be(address) != value:
        write_memory(address, int(value).to_bytes(2, "big"))


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


def _validated_object_pointer(value: int, label: str, *, allow_null: bool = False) -> int:
    if not isinstance(value, int) or not 0 <= value <= 0xFFFFFFFF:
        raise RuntimeError(f"{label} is not an unsigned 32-bit value: {value!r}")
    if allow_null and value == 0:
        return value
    if not _plausible_pointer(value):
        raise RuntimeError(f"{label} is not a plausible Wii pointer: 0x{value:08X}")
    return value


class ObjectMemoryReadError(RuntimeError):
    def __init__(self, address: int, label: str, error: Exception) -> None:
        self.address = address
        super().__init__(f"Could not read {label} at 0x{address:08X}: {error}")


def _read_object_u32(address: int, label: str) -> int:
    _validated_object_pointer(address, f"Address for {label}")
    try:
        return read_u32_be(address)
    except Exception as error:
        raise ObjectMemoryReadError(address, label, error) from error


def _format_object_resolver_trace(ctx: CreateContext) -> str:
    trace = getattr(ctx, "_object_resolver_trace", {})
    return ", ".join(f"{name}=0x{value:08X}" for name, value in trace.items())


def object_system_data(ctx: CreateContext) -> dict[str, Any]:
    return ctx.slot_data.get("ram", {}).get("object_system", {})


def find_first_object_node(ctx: CreateContext) -> int:
    object_system = object_system_data(ctx)
    registry_root = _int_from_hexish(object_system.get("registry_root"), 0x8066EA00)
    registry_key = _int_from_hexish(object_system.get("registry_key"), 0xA7390852)

    ctx._object_resolver_trace = {"registry_root": registry_root}
    entry = _read_object_u32(registry_root, "registry first entry")
    ctx._object_resolver_trace["registry_first_entry"] = entry
    for _ in range(512):
        if not entry:
            break
        _validated_object_pointer(entry, "Object registry entry pointer")
        ctx._object_resolver_trace["registry_entry"] = entry
        entry_key = _read_object_u32(entry + 0x0C, "registry entry key")
        ctx._object_resolver_trace["registry_entry_key"] = entry_key
        if entry_key == registry_key:
            ctx._object_resolver_trace["matching_entry"] = entry
            node = _read_object_u32(entry + 0x2C, "first Object node pointer")
            _validated_object_pointer(node, "First Object node pointer")
            ctx._object_resolver_trace["first_object_node"] = node
            return node
        entry = _read_object_u32(entry + 0x28, "next registry entry pointer")
        _validated_object_pointer(entry, "Next Object registry entry pointer", allow_null=True)
        ctx._object_resolver_trace["registry_next"] = entry
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
        _validated_object_pointer(node, f"Object node {object_id} pointer")
        seen_nodes.add(node)
        record = _read_object_u32(node + 0x10, f"Object {object_id} Availability Record pointer")
        _validated_object_pointer(record, f"Availability record for Object ID {object_id}")
        records[object_id] = record
        next_node = _read_object_u32(node + 0x14, f"Object node {object_id} next pointer")
        _validated_object_pointer(next_node, f"Object node {object_id} next pointer", allow_null=True)
        if object_id < 2:
            ctx._object_resolver_trace[f"node_{object_id}"] = node
            ctx._object_resolver_trace[f"node_{object_id}_record"] = record
            ctx._object_resolver_trace[f"node_{object_id}_next"] = next_node
        if object_id in (13, 126):
            ctx._object_resolver_trace[f"object_{object_id}_record"] = record
        node = next_node
    if len(set(records.values())) != OBJECT_RECORD_COUNT:
        raise RuntimeError("Object list contains duplicate Availability Record pointers.")
    return records


def object_records(ctx: CreateContext) -> dict[int, int] | None:
    if len(ctx._object_records) == OBJECT_RECORD_COUNT:
        return ctx._object_records
    if time.monotonic() < ctx._object_resolver_retry_at:
        return None
    recovering = ctx._object_resolver_failure_logged
    try:
        ctx._object_records = resolve_object_records(ctx)
        ctx._object_resolver_retry_at = 0.0
        ctx._object_resolver_failure_logged = False
        ctx._object_mem2_rehook_attempts = 0
        if recovering:
            logger.info("Create Object availability records resolved; Object RAM sync resumed.")
    except Exception as error:
        ctx._object_records = {}
        ctx._object_resolver_retry_at = time.monotonic() + OBJECT_RESOLVER_RETRY_SECONDS
        if (
            isinstance(error, ObjectMemoryReadError)
            and 0x90000000 <= error.address <= 0x93FFFFFF
            and ctx._object_mem2_rehook_attempts < OBJECT_MEM2_REHOOK_LIMIT
        ):
            ctx._object_mem2_rehook_requested = True
        if not ctx._object_resolver_failure_logged:
            logger.warning(
                "Create Object availability records are not ready; "
                f"Object RAM sync will retry automatically: {error}. "
                f"Resolver trace: {_format_object_resolver_trace(ctx)}"
            )
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

    guard = _address(ctx.slot_data["ram"]["addresses"]["save_slot_guard_primary"])
    try:
        value = read_u8(guard)
    except Exception:
        value = None  # A failed read also invalidates the current observation.

    if value == 2:
        if not ctx._slot_guard_observed_this_session:
            ctx._slot_guard_observed_this_session = True
            ctx.start_slot_settle()
        if not ctx.slot_ram_is_settled():
            ctx.save_slot_armed = False
            return
        if not ctx.save_slot_armed:
            ctx._hub_event_ready_at = time.monotonic() + HUB_EVENT_GRACE_SECONDS
        ctx.save_slot_armed = True
        if not ctx._slot_connected_logged:
            logger.info("Save Slot 3 connected.")
            ctx._slot_connected_logged = True
        return

    if value == 0xFF and ctx._slot_guard_observed_this_session:
        if not ctx.save_slot_armed and ctx.slot_ram_is_settled():
            ctx._hub_event_ready_at = time.monotonic() + HUB_EVENT_GRACE_SECONDS
            if not ctx._slot_connected_logged:
                logger.info("Save Slot 3 connected.")
                ctx._slot_connected_logged = True
        ctx.save_slot_armed = ctx.slot_ram_is_settled()
        return

    if not ctx.save_slot_armed and not ctx._waiting_for_slot_logged:
        logger.info("Waiting for Save Slot 3")
        ctx._waiting_for_slot_logged = True
    ctx.save_slot_armed = False
    ctx._slot_guard_observed_this_session = False
    ctx._slot_ready_at = 0.0
    ctx._slot_settle_logged = False
    ctx._slot_connected_logged = False
    if getattr(ctx, "_popup_runtime", None):
        ctx._popup_runtime.uninstall(read_memory, write_memory)
        ctx._popup_runtime_ready = False


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
        previous = ctx._previous_hub_challenge_sparks
        ctx._previous_hub_challenge_sparks = earned
        if earned == 0:
            ctx._hub_challenge_spark_armed = True
            return
        if (
            ctx._hub_challenge_spark_armed
            and previous == 0
            and earned > 0
            and time.monotonic() >= ctx._hub_event_ready_at
        ):
            checked_location(ctx, "Hub World Challenge 1 - Reward", newly_checked)
            ctx._hub_challenge_spark_armed = False
        return
    ctx._hub_challenge_spark_armed = False
    ctx._previous_hub_challenge_sparks = None

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


def check_hub_create_chain_parts(ctx: CreateContext, newly_checked: set[int]) -> None:
    if current_world_id(ctx) != 1:
        ctx._hub_chain_part_sequence = None
        return
    address = ctx.slot_data["ram"]["addresses"].get("hub_create_chain_part")
    if address is None:
        return
    value = read_u8(_address(address))
    previous = ctx._hub_chain_part_sequence
    if value == 0:
        ctx._hub_chain_part_sequence = 0
    elif previous is not None and value == previous:
        pass  # Repeated polls do not interrupt the sequence.
    elif previous in (0, 1) and value == previous + 1:
        ctx._hub_chain_part_sequence = value
    elif previous == 2 and value >= 3:
        checked_location(ctx, "Hub World Create Chain Part 3", newly_checked)
        ctx._hub_chain_part_sequence = None
    else:
        ctx._hub_chain_part_sequence = None
    if value in (1, 2):
        checked_location(ctx, f"Hub World Create Chain Part {value}", newly_checked)


def check_create_chain(ctx: CreateContext, newly_checked: set[int]) -> None:
    check_hub_create_chain_parts(ctx, newly_checked)
    world_id = current_world_id(ctx)
    if world_id != 1 and not ctx.slot_data["options"].get("create_chain_checks", True):
        return
    if world_id == 1:
        if current_challenge_raw(ctx) != 10:
            return
        event_key = (None, 1)
        if event_key not in ctx._chain_events_seen:
            checked_location(ctx, "Hub World Create Chain", newly_checked)
            checked_location(ctx, "Starting World Unlock", newly_checked)
            ctx._chain_events_seen.add(event_key)
            ctx._object_resync_blocked_until = time.monotonic() + OBJECT_RESYNC_AFTER_CHAIN_DELAY_SECONDS
            ctx._object_resync_pending = True
        return

    world_key = current_world_key(ctx)
    chain_index = None
    if world_key is not None:
        chain_index = read_u8(_address(ctx.slot_data["ram"]["addresses"]["create_chain_index"]))

    completion_flag = read_u8(_address(ctx.slot_data["ram"]["addresses"]["create_chain_completion"]))
    context_key = (world_key, chain_index)
    if ctx._chain_completion_context != context_key:
        ctx._chain_completion_context = context_key
        ctx._previous_chain_completion = completion_flag
        ctx._chain_context_ready_at = time.monotonic() + CHAIN_CONTEXT_SETTLE_SECONDS
        ctx._chain_event_armed_contexts.discard(context_key)
        return
    if time.monotonic() < ctx._chain_context_ready_at:
        ctx._previous_chain_completion = completion_flag
        return
    if completion_flag == 0:
        ctx._chain_event_armed_contexts.add(context_key)

    previous_completion = ctx._previous_chain_completion
    ctx._previous_chain_completion = completion_flag
    if (
        previous_completion is None
        or previous_completion == 1
        or completion_flag != 1
        or context_key not in ctx._chain_event_armed_contexts
    ):
        return

    if world_key is not None:
        chain = max(1, min(5, (chain_index or 0) + 1))
        event_key = (world_key, chain)
        if event_key not in ctx._chain_events_seen:
            world_name = ctx.slot_data["worlds"][world_key]["name"]
            checked_location(ctx, f"{world_name} Create Chain {chain}", newly_checked)
            ctx._chain_events_seen.add(event_key)
            ctx._chain_event_armed_contexts.discard(context_key)
            ctx._object_resync_blocked_until = time.monotonic() + OBJECT_RESYNC_AFTER_CHAIN_DELAY_SECONDS
            ctx._object_resync_pending = True


def check_spark_goal_world_unlock(ctx: CreateContext, newly_checked: set[int]) -> None:
    required_sparks = int(ctx.slot_data.get("required_sparks", 0))
    spark_goal_mode = ctx.slot_data.get("spark_goal_mode") or ctx.slot_data.get("options", {}).get("spark_goal_mode")
    if (
        required_sparks > 0
        and spark_goal_mode == "goal_world_unlock"
        and received_spark_count(ctx) >= required_sparks
    ):
        checked_location(ctx, "Spark Requirement Met", newly_checked)


def location_context_is_settled(ctx: CreateContext) -> bool:
    world_id = current_world_id(ctx)
    context = (world_id, current_world_key(ctx))
    if ctx._location_context != context:
        ctx._location_context = context
        ctx._hub_chain_part_sequence = None
        ctx._location_context_ready_at = time.monotonic() + WORLD_CONTEXT_SETTLE_SECONDS
        ctx._location_context_logged = False
        ctx._chain_completion_context = None
        ctx._previous_chain_completion = None
        ctx._chain_context_ready_at = 0.0
        return False

    remaining = ctx._location_context_ready_at - time.monotonic()
    if remaining <= 0:
        return True
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
        check_spark_goal_world_unlock(ctx, newly_checked)
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

    # The global Object list is not stable/readable while a challenge is active.
    # Resolve and write its Availability Records only after returning to a world.
    if challenge_active:
        return

    now = time.monotonic()
    if now < ctx._object_resync_blocked_until:
        ctx._object_resync_pending = True
        return
    if (
        not ctx._object_resync_pending
        and now - ctx._last_object_resync_at < OBJECT_RESYNC_INTERVAL_SECONDS
    ):
        return

    records = object_records(ctx)
    if not records:
        return

    try:
        for object_data in ctx.slot_data.get("objects", {}).values():
            object_id = int(object_data["global_value"])
            record = records.get(object_id)
            if not record:
                continue
            if object_id in owned_values:
                apply_owned_object_record(record)
            else:
                apply_unowned_object_record(record)
    except Exception as error:
        ctx._object_records = {}
        ctx._object_resync_pending = True
        ctx._object_resolver_retry_at = now + OBJECT_RESOLVER_RETRY_SECONDS
        if not ctx._object_resolver_failure_logged:
            logger.warning(
                "Create Object availability records changed while syncing; "
                f"Object RAM sync will retry automatically: {error}"
            )
            ctx._object_resolver_failure_logged = True
        return

    ctx._object_resync_pending = False
    ctx._last_object_resync_at = now


def popup_object_name(ctx: CreateContext, object_id: int) -> str:
    return next((data.get("name", name) for name, data in ctx.slot_data.get("objects", {}).items()
                 if int(data["global_value"]) == object_id), str(object_id))


def collect_new_object_popup_items(ctx: CreateContext) -> None:
    if not ctx._popup_accept_new_items:
        return
    if ctx._popup_item_cursor > len(ctx.items_received):
        # An AP resync replaced the receipt list. Establish a fresh baseline.
        ctx._popup_item_cursor = len(ctx.items_received)
        return
    while ctx._popup_item_cursor < len(ctx.items_received):
        item = ctx.items_received[ctx._popup_item_cursor]
        ctx._popup_item_cursor += 1
        name = item_name_from_network(ctx, item.item)
        data = ctx.slot_data.get("objects", {}).get(name)
        if not data:
            continue
        try:
            value = int(data["global_value"])
        except (KeyError, TypeError, ValueError):
            logger.warning("Ignoring invalid popup Object data for %s.", name)
            continue
        if 0 <= value < OBJECT_RECORD_COUNT:
            ctx._object_popup_queue.append(value)
            logger.info("Queued Object popup: %s (ID %d).", name, value)


def service_object_popup_queue(ctx: CreateContext, challenge_active: bool) -> None:
    if not ctx._popup_runtime_ready or not ctx.save_slot_armed or challenge_active:
        return
    runtime = ctx._popup_runtime
    state = runtime.snapshot(read_memory)
    status = state["status"]
    if status != ctx._popup_last_status:
        if status == ACTIVE:
            logger.info("Showing AP Object popup: %s (ID %d).",
                        popup_object_name(ctx, state["object_id"]), state["object_id"])
        elif status == ERROR:
            logger.warning("AP Object popup runtime error %d, request %d, Object %d; popup dispatch stopped.",
                           state["error"], state["request_seq"], state["object_id"])
        ctx._popup_last_status = status
    if ctx._popup_inflight:
        value, sequence = ctx._popup_inflight
        if state["ack_seq"] == sequence and status == IDLE:
            logger.info("AP Object popup closed.")
            ctx._popup_inflight = None
        elif status == IDLE:
            # A pending request was cancelled during a transition.
            ctx._object_popup_queue.appendleft(value)
            ctx._popup_inflight = None
        else:
            return
    if status != IDLE or not ctx._object_popup_queue or ctx._object_resync_pending:
        return
    if time.monotonic() < ctx._object_resync_blocked_until:
        return
    if read_u32_be(MODAL_LAYER):
        if not ctx._popup_delay_logged:
            logger.info("Create AP Object popup delayed: another modal UI is active.")
            ctx._popup_delay_logged = True
        return
    ctx._popup_delay_logged = False
    records = object_records(ctx)
    value = ctx._object_popup_queue[0]
    if not records or value not in records:
        return
    apply_owned_object_record(records[value])
    if runtime.request_object(value, read_memory, write_memory):
        ctx._object_popup_queue.popleft()
        ctx._popup_inflight = (value, runtime.snapshot(read_memory)["request_seq"])


def sync_object_popups(ctx: CreateContext, challenge_active: bool) -> None:
    if not ctx.save_slot_armed or not ctx.ram_is_settled() or not ctx.slot_ram_is_settled():
        return
    # Capture the receipt baseline after the first successful availability sync,
    # independently of heartbeat readiness so items arriving during that probe
    # are still retained in receipt order.
    if not ctx._popup_accept_new_items and not ctx._object_resync_pending and ctx._object_records:
        ctx._popup_item_cursor = len(ctx.items_received)
        ctx._popup_accept_new_items = True
    collect_new_object_popup_items(ctx)
    if challenge_active:
        # Do not let an already-published request survive into an unsafe Object
        # registry. Active UI owners are always left to vanilla cleanup.
        if ctx._popup_runtime.installed:
            ctx._popup_runtime.reset_request(read_memory, write_memory)
        return
    if ctx._object_resync_pending or not ctx._object_records:
        return
    ctx._popup_runtime_ready = ctx._popup_runtime.ensure_installed(read_memory, write_memory)
    service_object_popup_queue(ctx, challenge_active)


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
    hub_chain_complete = hub_create_chain_done(ctx)
    records = ctx.slot_data["ram"]["challenge_records"]
    for world_key, world_data in ctx.slot_data.get("worlds", {}).items():
        unlocked = 1 if hub_chain_complete and world_key in owned_worlds else 0
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
    required_sparks = int(ctx.slot_data.get("required_sparks", 0))
    if not ctx.save_slot_armed or required_sparks <= 0:
        return
    total_sparks_address = _address(ctx.slot_data["ram"]["addresses"]["total_sparks"])
    write_u32_be_if_changed(total_sparks_address, min(received_spark_count(ctx), 610))


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
        try:
            resolved = _read_challenge_object_list_candidate(candidate)
        except (RuntimeError, OSError):
            continue
        if resolved is None:
            continue
        entries, count = resolved
        if count >= expected_count:
            return entries, count
    return None


def filter_current_challenge_palette(ctx: CreateContext, challenge_active: bool) -> bool:
    try:
        return _filter_current_challenge_palette(ctx, challenge_active)
    except (RuntimeError, OSError):
        if not ctx._challenge_palette_failure_logged:
            logger.debug("Create challenge Object palette is temporarily unreadable; retrying.")
            ctx._challenge_palette_failure_logged = True
        return False


def _filter_current_challenge_palette(ctx: CreateContext, challenge_active: bool) -> bool:
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
        if selected_value >= count:
            continue
        key_address = entries + selected_value * CHALLENGE_OBJECT_ENTRY_STRIDE + 0x04
        current_key = read_u32_be(key_address)
        if current_key:
            ctx._challenge_palette_keys[global_value] = current_key
        if global_value in owned_values:
            original_key = ctx._challenge_palette_keys.get(global_value)
            if original_key:
                write_u32_be_if_changed(key_address, original_key)
        else:
            write_u32_be_if_changed(key_address, 0)

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
    spark_goal_mode = ctx.slot_data.get("spark_goal_mode") or ctx.slot_data.get("options", {}).get("spark_goal_mode")
    spark_count = received_spark_count(ctx)
    if required_sparks > 0 and spark_goal_mode == "spark_hunt" and spark_count >= required_sparks:
        Utils.async_start(ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}]))
        ctx.finished_game = True
        return
    if ITEM_VICTORY in received_item_names(ctx) and spark_count >= required_sparks:
        Utils.async_start(ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}]))
        ctx.finished_game = True


async def dolphin_sync_task(ctx: CreateContext) -> None:
    import dolphin_memory_engine

    reset_mem2_fallback()
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
                    sync_object_availability(ctx, challenge_active)
                    sync_object_popups(ctx, challenge_active)
                    if ctx._object_mem2_rehook_requested:
                        ctx._object_mem2_rehook_requested = False
                        ctx._object_mem2_rehook_attempts += 1
                        logger.info(
                            "Create Object MEM2 was unavailable; reconnecting to Dolphin "
                            f"to rediscover it ({ctx._object_mem2_rehook_attempts}/{OBJECT_MEM2_REHOOK_LIMIT})."
                        )
                        ctx._popup_runtime.uninstall(read_memory, write_memory)
                        dolphin_memory_engine.un_hook()
                        ctx.dolphin_status = CONNECTION_LOST_STATUS
                        ctx.start_ram_settle()
                        sleep_time = 1
                        continue
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
            try:
                if (dolphin_memory_engine.is_hooked()
                        and dolphin_memory_engine.read_bytes(GAME_ID_ADDRESS, 6) in SUPPORTED_GAME_IDS):
                    ctx._popup_runtime.uninstall(read_memory, write_memory)
            except Exception:
                logger.debug("Popup cleanup unavailable after Dolphin error.", exc_info=True)
            dolphin_memory_engine.un_hook()
            ctx.dolphin_status = CONNECTION_LOST_STATUS
            ctx.start_ram_settle()
            logger.error(traceback.format_exc())
            sleep_time = 5

    if dolphin_memory_engine.is_hooked() and ctx.dolphin_status == CONNECTION_CONNECTED_STATUS:
        ctx._popup_runtime.uninstall(read_memory, write_memory)
    reset_mem2_fallback()


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
