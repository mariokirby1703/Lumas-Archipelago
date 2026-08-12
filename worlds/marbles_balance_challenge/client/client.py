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

from ..Names import item_names, location_names
from ..world_constants import (
    BONUS_WORLDS,
    DIFFICULTIES,
    GAME_NAME,
    LEVELS_PER_WORLD,
    MARBLES,
    NORMAL_WORLDS,
    TRAPS,
    WORLD_INDEX_BY_DIFFICULTY,
)

ModuleUpdate.update()

CONNECTION_INITIAL_STATUS = "Dolphin connection has not been initiated."
CONNECTION_CONNECTED_STATUS = "Dolphin connected successfully."
CONNECTION_LOST_STATUS = "Dolphin connection was lost. Retrying..."
CONNECTION_REFUSED_GAME_STATUS = "Dolphin connected, but RK6P18 is not running. Load Marbles! Balance Challenge PAL."

GAME_ID_ADDRESS = 0x80000000
GAME_ID = b"RK6P18"

DIFFICULTY_INDEX = {"Easy": 0, "Normal": 1, "Hard": 2}
TROPHY_REQUIREMENTS = {
    "bronze_trophy": 1,
    "silver_trophy": 2,
    "gold_trophy": 3,
    "platinum_trophy": 4,
}
GOAL_REACHED_CANDIDATES = (
    0x90144168,
    0x901441AC,
    0x901441F0,
    0x90144234,
    0x90144278,
    0x901442BC,
    0x90144300,
    0x90144344,
    0x90144388,
    0x901443CC,
    0x90144410,
    0x90144454,
    0x90144498,
    0x901444DC,
    0x90144520,
    0x90144564,
    0x901445A8,
    0x901445EC,
    0x90144630,
    0x90459ED3,
    0x90459ED7,
)
GOAL_ENTER_THRESHOLD = 5
GOAL_EXIT_THRESHOLD = 1
STAGE_CLEARED_VALUES = {94, 95}
LEVEL_START_SEQUENCE_ADDRESS = 0x90155FDB
BLACKOUT_TRAP_DURATION = 10.0
INVERSE_TRAP_DURATION = 30.0
NOCLIP_TRAP_DURATION = 3.0
BONUS_VEHICLE_PICKUP_LEVELS = {
    ("Normal", "WA", 1),
    ("Normal", "WB", 1),
    ("Normal", "WB", 5),
    ("Normal", "WC", 1),
    ("Normal", "WC", 5),
}


class MarbleBalanceCommandProcessor(ClientCommandProcessor):
    ctx: "MarbleBalanceContext"

    def _cmd_dolphin(self) -> None:
        """Display the current Dolphin connection status."""
        logger.info(f"Dolphin Status: {self.ctx.dolphin_status}")

    def _cmd_mbc(self) -> None:
        """Display Marbles! Balance Challenge client status."""
        logger.info(
            f"{len(self.ctx.locations_checked)} local checks, "
            f"{self.ctx.processed_item_count}/{len(self.ctx.items_received)} received items processed."
        )


class MarbleBalanceContext(CommonContext):
    command_processor = MarbleBalanceCommandProcessor
    game = GAME_NAME
    items_handling = 0b111

    def __init__(self, server_address: str | None, password: str | None, patch_file: str | None = None) -> None:
        super().__init__(server_address, password)
        self.dolphin_status = CONNECTION_INITIAL_STATUS
        self.dolphin_sync_task: asyncio.Task[None] | None = None
        self.slot_data: dict[str, Any] = {}
        self.patch_data: dict[str, Any] = {}
        self.processed_item_count = 0
        self._logged_unsupported_items: set[str] = set()
        self._goal_reached_latched = False
        self._goal_latched_stage: tuple[str, str | None, str | None, int] | None = None
        self._goal_armed = True
        self._stage_cleared_armed = True
        self._last_stage_identity: tuple[str, str | None, str | None, int] | None = None
        self._stage_entered_at = 0.0
        self._countdown_stage_identity: tuple[str, str | None, str | None, int] | None = None
        self._countdown_next_value = 0
        self._countdown_ready = False
        self._previous_green_or_ant = 0
        self._previous_stump = 0
        self._previous_junk = 0
        self._pickup_events_seen_this_stage: set[str] = set()
        self.mirror_trap_pending = False
        self.mirror_trap_active = False
        self.mirror_active_since = 0.0
        self.mirror_active_stage: tuple[str, str | None, str | None, int] | None = None
        self.mirror_skip_stage: tuple[str, str | None, str | None, int] | None = None
        self.blackout_remaining = 0.0
        self.blackout_last_tick = time.monotonic()
        self.blackout_owned = False
        self.blackout_active = False
        self.blackout_active_since = 0.0
        self.blackout_next_log_at = 0.0
        self.blackout_delay_next_stage = False
        self.blackout_started = False
        self.inverse_trap_pending = False
        self.inverse_trap_active = False
        self.inverse_remaining = 0.0
        self.inverse_last_tick = time.monotonic()
        self.inverse_active_since = 0.0
        self.inverse_next_log_at = 0.0
        self.inverse_delay_next_stage = False
        self.noclip_remaining = 0.0
        self.noclip_last_tick = time.monotonic()
        self.noclip_owned = False
        self.noclip_active = False
        self.noclip_active_since = 0.0
        self.noclip_next_log_at = 0.0
        self.noclip_delay_next_stage = False
        self.noclip_skip_stage: tuple[str, str | None, str | None, int] | None = None
        self.noclip_rewrite_after_clear_until = 0.0
        self.noclip_rewrite_after_clear_done = False
        self.noclip_last_forced_zero_at = 0.0
        self.save_slot_ready = False
        self._save_slot_logged = False
        self._skip_existing_received_items = False

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
            self.processed_item_count = 0
            self._skip_existing_received_items = True
            self.locations_checked = set()
            self.save_slot_ready = False
            self._save_slot_logged = False
            logger.debug("Connected to Archipelago as Marbles! Balance Challenge.")

    async def disconnect(self, allow_autoreconnect: bool = False) -> None:
        self.slot_data = self.patch_data.get("slot_data", {})
        self.processed_item_count = 0
        self._skip_existing_received_items = True
        self._logged_unsupported_items.clear()
        self.save_slot_ready = False
        self._save_slot_logged = False
        await super().disconnect(allow_autoreconnect)

    def make_gui(self):
        ui = super().make_gui()
        ui.base_title = "Archipelago Marbles! Balance Challenge Client"
        return ui


def read_u8(address: int) -> int:
    import dolphin_memory_engine

    return dolphin_memory_engine.read_byte(address)


def read_u16_be(address: int) -> int:
    import dolphin_memory_engine

    return int.from_bytes(dolphin_memory_engine.read_bytes(address, 2), "big")


def write_u8(address: int, value: int) -> None:
    import dolphin_memory_engine

    dolphin_memory_engine.write_byte(address, value & 0xFF)


def ensure_u8(address: int | None, value: int = 1) -> None:
    if address is not None and read_u8(address) < value:
        write_u8(address, value)


def write_u8_if_changed(address: int | None, value: int) -> None:
    if address is not None and read_u8(address) != value:
        write_u8(address, value)


def add_u8(address: int | None, amount: int = 1, maximum: int = 99) -> int | None:
    if address is None:
        return None
    value = min(maximum, read_u8(address) + amount)
    write_u8(address, value)
    return value


def current_level_identity(slot_data: dict[str, Any]) -> tuple[str | None, str | None, int | None]:
    static = slot_data.get("static_addresses", {})
    try:
        world_index = read_u8(static["current_world_or_mode_index"])
        stage_index = read_u8(static["selected_stage_index"])
        difficulty_index = read_u8(static["difficulty_a"])
    except Exception:
        return None, None, None

    difficulty_lookup = {value: name for name, value in DIFFICULTY_INDEX.items()}
    difficulty = difficulty_lookup.get(difficulty_index)
    world_lookup = {
        index: world
        for world, index in WORLD_INDEX_BY_DIFFICULTY.get(difficulty, {}).items()
    }
    world = world_lookup.get(world_index)
    if world in BONUS_WORLDS and difficulty != "Hard":
        difficulty = "Normal"
    return difficulty, world, stage_index + 1


def current_stage(slot_data: dict[str, Any]) -> dict[str, Any] | None:
    static = slot_data.get("static_addresses", {})
    safety = slot_data.get("safety", {})
    try:
        world_index = read_u8(static["current_world_or_mode_index"])
        stage_index = read_u8(static["selected_stage_index"])
        difficulty_index = read_u8(static["difficulty_a"])
        game_mode = read_u8(static["current_game_mode"])
    except Exception:
        return None

    level = stage_index + 1
    if game_mode == safety.get("tutorial_stage_mode", 0x1F):
        return {"kind": "tutorial", "difficulty": None, "world": None, "level": level}

    if world_index == safety.get("balance_board_world_or_mode_index", 14):
        return {"kind": "balance_board", "difficulty": None, "world": None, "level": level}

    difficulty_lookup = {value: name for name, value in DIFFICULTY_INDEX.items()}
    difficulty = difficulty_lookup.get(difficulty_index)
    world_lookup = {
        index: world
        for world, index in WORLD_INDEX_BY_DIFFICULTY.get(difficulty, {}).items()
    }
    world = world_lookup.get(world_index)
    if world is None or difficulty is None:
        return None
    if world in BONUS_WORLDS and difficulty != "Hard":
        difficulty = "Normal"
    return {"kind": "stage", "difficulty": difficulty, "world": world, "level": level}


def stage_identity(stage: dict[str, Any] | None) -> tuple[str, str | None, str | None, int] | None:
    if stage is None:
        return None
    return (stage["kind"], stage.get("difficulty"), stage.get("world"), stage["level"])


def reset_stage_detectors(ctx: MarbleBalanceContext, stage: dict[str, Any] | None, now: float) -> None:
    static = ctx.slot_data.get("static_addresses", {})
    ctx._last_stage_identity = stage_identity(stage)
    ctx._stage_entered_at = now
    ctx._goal_reached_latched = False
    ctx._goal_latched_stage = None
    ctx._goal_armed = goal_active_count() <= GOAL_EXIT_THRESHOLD
    ctx._countdown_stage_identity = stage_identity(stage)
    ctx._countdown_next_value = 0
    ctx._countdown_ready = False
    stage_cleared_flag = static.get("stage_cleared_flag")
    try:
        ctx._stage_cleared_armed = stage_cleared_flag is None or read_u8(stage_cleared_flag) not in STAGE_CLEARED_VALUES
    except Exception:
        ctx._stage_cleared_armed = False
    try:
        ctx._previous_green_or_ant = read_u8(static["green_or_ant_temporary_pickup"])
        ctx._previous_stump = read_u8(static["stump_temporary_pickup"])
        ctx._previous_junk = read_u8(static["junk_temporary_pickup"])
        ctx._pickup_events_seen_this_stage = set()
    except Exception:
        ctx._previous_green_or_ant = 0
        ctx._previous_stump = 0
        ctx._previous_junk = 0
        ctx._pickup_events_seen_this_stage = set()


def in_level_active(slot_data: dict[str, Any]) -> bool:
    static = slot_data.get("static_addresses", {})
    try:
        return read_u8(static["in_game_indicator"]) == 1
    except Exception:
        return False


def campaign_stage_active(slot_data: dict[str, Any]) -> bool:
    static = slot_data.get("static_addresses", {})
    safety = slot_data.get("safety", {})
    try:
        return read_u8(static["current_game_mode"]) == safety.get("world_map_stage_mode", 0x1D)
    except Exception:
        return False


def goal_or_result_active(slot_data: dict[str, Any]) -> bool:
    static = slot_data.get("static_addresses", {})
    stage_cleared = static.get("stage_cleared_flag")
    if stage_cleared is not None:
        try:
            if read_u8(stage_cleared) in STAGE_CLEARED_VALUES:
                return True
        except Exception:
            pass
    return goal_active_count() >= GOAL_ENTER_THRESHOLD


def level_countdown_ready(ctx: MarbleBalanceContext, stage: dict[str, Any] | None) -> bool:
    identity = stage_identity(stage)
    if stage is None or not in_level_active(ctx.slot_data):
        ctx._countdown_stage_identity = None
        ctx._countdown_next_value = 0
        ctx._countdown_ready = False
        return False

    if identity != ctx._countdown_stage_identity:
        ctx._countdown_stage_identity = identity
        ctx._countdown_next_value = 0
        ctx._countdown_ready = False

    try:
        countdown = read_u8(LEVEL_START_SEQUENCE_ADDRESS)
    except Exception:
        return False

    if ctx._countdown_ready:
        return True

    expected = ctx._countdown_next_value
    if countdown == expected:
        if expected == 3:
            ctx._countdown_ready = True
        else:
            ctx._countdown_next_value = expected + 1
    elif countdown == 0:
        ctx._countdown_next_value = 1
    elif countdown != max(0, expected - 1):
        ctx._countdown_next_value = 0

    if ctx._countdown_ready:
        logger.debug(f"Level start sequence complete at 0x{LEVEL_START_SEQUENCE_ADDRESS:08X}=3; traps may fire.")
        ctx._countdown_ready = True

    return ctx._countdown_ready


def trap_safe_gameplay(ctx: MarbleBalanceContext, stage: dict[str, Any] | None) -> bool:
    return (
        stage is not None
        and in_level_active(ctx.slot_data)
        and level_countdown_ready(ctx, stage)
        and not goal_or_result_active(ctx.slot_data)
        and goal_active_count() < GOAL_ENTER_THRESHOLD
    )


def trap_delay_elapsed(ctx: MarbleBalanceContext) -> bool:
    return level_countdown_ready(ctx, current_stage(ctx.slot_data))


def target_save_slot_active(slot_data: dict[str, Any]) -> bool:
    static = slot_data.get("static_addresses", {})
    safety = slot_data.get("safety", {})
    try:
        return read_u8(static["selected_save_slot"]) == safety.get("target_save_slot_index", 2)
    except Exception:
        return False


def sync_save_slot_guard(ctx: MarbleBalanceContext) -> None:
    if target_save_slot_active(ctx.slot_data):
        if not ctx.save_slot_ready:
            reset_stage_detectors(ctx, current_stage(ctx.slot_data), asyncio.get_running_loop().time())
            ctx.locations_checked = set()
            ctx.save_slot_ready = True
            logger.info("Save Slot 3 entered. Location sending is now enabled.")
        return

    if ctx.save_slot_ready:
        logger.info("Save Slot 3 left. Location sending is paused.")
    elif not ctx._save_slot_logged:
        logger.info("Waiting for Save Slot 3 before sending locations.")
        ctx._save_slot_logged = True
    ctx.save_slot_ready = False


def is_current_location(location: dict[str, Any], slot_data: dict[str, Any]) -> bool:
    difficulty, world, level = current_level_identity(slot_data)
    return (
        location.get("difficulty") == difficulty
        and location.get("world") == world
        and location.get("level") == level
    )


def goal_active_count() -> int:
    count = 0
    for address in GOAL_REACHED_CANDIDATES:
        try:
            if read_u8(address) == 1:
                count += 1
        except Exception:
            pass
    return count


def update_goal_reached(ctx: MarbleBalanceContext, stage: dict[str, Any] | None, now: float) -> bool:
    identity = stage_identity(stage)
    if identity is None or not in_level_active(ctx.slot_data):
        ctx._goal_reached_latched = False
        ctx._goal_latched_stage = None
        return False

    count = goal_active_count()
    if count <= GOAL_EXIT_THRESHOLD:
        ctx._goal_reached_latched = False
        ctx._goal_latched_stage = None
        ctx._goal_armed = True
        return False

    if not ctx._goal_armed or now - ctx._stage_entered_at < 5.0:
        return False

    if not ctx._goal_reached_latched and count >= GOAL_ENTER_THRESHOLD:
        ctx._goal_reached_latched = True
        ctx._goal_latched_stage = identity
        ctx._goal_armed = False
        return True
    return ctx._goal_reached_latched and ctx._goal_latched_stage == identity


def location_is_checked(
    ctx: MarbleBalanceContext,
    location: dict[str, Any],
    slot_data: dict[str, Any],
    stage: dict[str, Any] | None,
    now: float,
) -> bool:
    category = location.get("category")
    addresses = location.get("addresses") or {}

    if category == "tutorial":
        safety = slot_data.get("safety", {})
        return (
            stage is not None
            and stage["kind"] == "tutorial"
            and in_level_active(slot_data)
            and stage["level"] == location.get("level")
            and update_goal_reached(ctx, stage, now)
            and read_u8(slot_data["static_addresses"]["current_game_mode"]) == safety.get("tutorial_stage_mode", 0x1F)
        )

    if category == "balance_board":
        return (
            stage is not None
            and stage["kind"] == "balance_board"
            and in_level_active(slot_data)
            and stage["level"] == location.get("level")
            and update_goal_reached(ctx, stage, now)
        )

    if category in {"goal", "bonus_goal"}:
        if (
            in_level_active(slot_data)
            and is_current_location(location, slot_data)
            and update_goal_reached(ctx, stage, now)
        ):
            return True
        if (
            is_current_location(location, slot_data)
            and in_level_active(slot_data)
            and (
                location.get("level") == 11
                or location.get("world") == "W7"
                and location.get("level") == 10
            )
            and addresses.get("state") is not None
            and read_u8(addresses["state"]) == 3
        ):
            return True
        return (
            is_current_location(location, slot_data)
            and in_level_active(slot_data)
            and location.get("level") == 11
            and (addresses.get("trophy") is not None and read_u8(addresses["trophy"]) > 0)
        )

    if category in TROPHY_REQUIREMENTS:
        trophy = addresses.get("trophy")
        mirror_trophy = addresses.get("mirror_trophy")
        requirement = TROPHY_REQUIREMENTS[category]
        return (
            trophy is not None and read_u8(trophy) >= requirement
            or mirror_trophy is not None and read_u8(mirror_trophy) >= requirement
        )

    if category == "counter_stump_unlock":
        required = slot_data.get("options", {}).get("required_stump_pieces_for_w7", 60)
        return received_item_names(ctx).count(item_names.STUMP_TEMPLE_PIECE) >= required

    if category == "counter_hard_mode":
        required = slot_data.get("options", {}).get("required_green_gems_for_hard", 30)
        return received_item_names(ctx).count(item_names.GREEN_GEM) >= required

    if category in {"green_gem", "stump_piece"}:
        if category == "stump_piece":
            return False
        address = addresses.get(category)
        return address is not None and read_u8(address) > 0

    if category == "ant":
        ant = addresses.get("ant")
        return ant is not None and read_u8(ant) > 0

    return False


def poll_pickup_locations(  # noqa: C901
    ctx: MarbleBalanceContext,
    stage: dict[str, Any] | None,
) -> list[str]:
    if stage is None:
        return []

    static = ctx.slot_data.get("static_addresses", {})
    try:
        green_or_ant = read_u8(static["green_or_ant_temporary_pickup"])
        stump = read_u8(static["stump_temporary_pickup"])
        junk = read_u8(static["junk_temporary_pickup"])
    except Exception:
        return []

    events: list[str] = []
    difficulty = stage.get("difficulty")
    world = stage.get("world")
    level = stage["level"]

    if ctx._previous_green_or_ant == 0 and green_or_ant == 1 and stage["kind"] == "stage" and level <= 10:
        if difficulty in {"Easy", "Normal"} and world in NORMAL_WORLDS:
            events.append(location_names.green_gem_location_name(difficulty, world, level))
        elif difficulty == "Hard":
            events.append(location_names.ant_location_name(difficulty, world, level))

    if stump != 0 and stage["kind"] == "stage":
        if difficulty in {"Easy", "Normal"} and world in NORMAL_WORLDS[:6] and level <= 10:
            expected = NORMAL_WORLDS.index(world) * 10 + level
            if stump == expected:
                events.append(location_names.stump_piece_location_name(difficulty, world, level))

    if junk != 0 and stage["kind"] == "stage" and level <= 10:
        if difficulty == "Hard" and world in NORMAL_WORLDS[:6]:
            events.append(location_names.stump_piece_location_name(difficulty, world, level))
        elif world in BONUS_WORLDS:
            events.append(location_names.stump_piece_location_name(difficulty, world, level))

    ctx._previous_green_or_ant = green_or_ant
    ctx._previous_stump = stump
    ctx._previous_junk = junk
    valid_events = []
    for event in events:
        in_slot = event in ctx.slot_data.get("locations", {})
        if in_slot and event not in ctx._pickup_events_seen_this_stage:
            valid_events.append(event)
            ctx._pickup_events_seen_this_stage.add(event)
    return valid_events


async def check_locations(ctx: MarbleBalanceContext) -> None:  # noqa: C901
    if not ctx.slot_data or not ctx.save_slot_ready:
        return

    now = asyncio.get_running_loop().time()
    stage = current_stage(ctx.slot_data)
    identity = stage_identity(stage)
    if identity != ctx._last_stage_identity or not in_level_active(ctx.slot_data):
        reset_stage_detectors(ctx, stage, now)
        return
    if stage is not None and stage["kind"] == "stage" and not campaign_stage_active(ctx.slot_data):
        reset_stage_detectors(ctx, stage, now)
        return

    stage_cleared_flag = ctx.slot_data.get("static_addresses", {}).get("stage_cleared_flag")
    if stage_cleared_flag is not None:
        try:
            if read_u8(stage_cleared_flag) not in STAGE_CLEARED_VALUES:
                ctx._stage_cleared_armed = True
        except Exception:
            pass

    newly_checked: set[int] = set()
    for location_name in poll_pickup_locations(ctx, stage):
        location = ctx.slot_data.get("locations", {}).get(location_name)
        location_id = location.get("id") if location else None
        if location_id and location_id not in ctx.locations_checked:
            ctx.locations_checked.add(location_id)
            newly_checked.add(location_id)
            logger.debug(f"Checked: {location_name}")

    for location_name, location in ctx.slot_data.get("locations", {}).items():
        location_id = location.get("id")
        if not location_id or location_id in ctx.locations_checked:
            continue
        try:
            if location_is_checked(ctx, location, ctx.slot_data, stage, now):
                ctx.locations_checked.add(location_id)
                newly_checked.add(location_id)
                logger.debug(f"Checked: {location_name}")
                if location.get("category") in TROPHY_REQUIREMENTS and location.get("level") == 11:
                    goal_name = location_names.goal_location_name(
                        location["difficulty"],
                        location["world"],
                        location["level"],
                    )
                    goal_location = ctx.slot_data.get("locations", {}).get(goal_name)
                    goal_id = goal_location.get("id") if goal_location else None
                    if goal_id and goal_id not in ctx.locations_checked:
                        ctx.locations_checked.add(goal_id)
                        newly_checked.add(goal_id)
                        logger.debug(f"Checked: {goal_name}")
        except Exception:
            logger.debug("Failed to read location %s.", location_name, exc_info=True)

    if newly_checked and ctx.slot is not None:
        await ctx.send_msgs([{"cmd": "LocationChecks", "locations": list(newly_checked)}])


def item_name_from_network(ctx: MarbleBalanceContext, item_id: int) -> str | None:
    try:
        return ctx.item_names.lookup_in_game(item_id, ctx.game)
    except Exception:
        return None


def world_unlocks() -> dict[str, tuple[str, str]]:
    unlocks = {
        item_names.world_access_name(difficulty, world): (difficulty, world)
        for difficulty in DIFFICULTIES
        for world in NORMAL_WORLDS
    }
    for difficulty in ("Normal", "Hard"):
        for world in BONUS_WORLDS:
            unlocks[item_names.world_access_name(difficulty, world)] = (difficulty, world)
    return unlocks


WORLD_UNLOCKS = world_unlocks()


def unlock_matching_levels(slot_data: dict[str, Any], difficulty: str, world: str, levels: range) -> None:
    for location in slot_data.get("locations", {}).values():
        if (
            location.get("category") in {"goal", "bonus_goal"}
            and location.get("difficulty") == difficulty
            and location.get("world") == world
            and location.get("level") in levels
        ):
            address = (location.get("addresses") or {}).get("state")
            if address is not None and read_u8(address) == 0:
                write_u8(address, 1)


def set_matching_levels(slot_data: dict[str, Any], difficulty: str, world: str, levels: range, value: int) -> None:
    for location in slot_data.get("locations", {}).values():
        if (
            location.get("category") == "goal"
            and location.get("difficulty") == difficulty
            and location.get("world") == world
            and location.get("level") in levels
        ):
            address = (location.get("addresses") or {}).get("state")
            current = read_u8(address) if address is not None else value
            if address is not None and value == 1 and current == 0:
                write_u8(address, value)
            elif address is not None and value == 0 and current in {1, 2}:
                write_u8(address, value)


def force_matching_level_states(
    slot_data: dict[str, Any],
    difficulty: str,
    world: str,
    levels: range,
    from_values: set[int],
    value: int,
) -> None:
    for location in slot_data.get("locations", {}).values():
        if (
            location.get("category") == "goal"
            and location.get("difficulty") == difficulty
            and location.get("world") == world
            and location.get("level") in levels
        ):
            address = (location.get("addresses") or {}).get("state")
            if address is not None and read_u8(address) in from_values:
                write_u8(address, value)


def received_item_names(ctx: MarbleBalanceContext) -> list[str]:
    names: list[str] = []
    for network_item in ctx.items_received:
        item_name = item_name_from_network(ctx, network_item.item)
        if item_name:
            names.append(item_name)
    return names


def goal_difficulty(slot_data: dict[str, Any]) -> str:
    goal = slot_data.get("options", {}).get("goal")
    return "Hard" if goal in {"hard_w7_l10", "stump_temple_level_10_hard", 1} else "Normal"


def granted_normal_worlds(ctx: MarbleBalanceContext) -> set[tuple[str, str]]:
    slot_data = ctx.slot_data
    granted = {
        (difficulty, world)
        for difficulty, world in slot_data.get("starting_worlds", {}).items()
        if world in NORMAL_WORLDS
    }

    item_names_received = received_item_names(ctx)
    for item_name in item_names_received:
        if item_name in WORLD_UNLOCKS:
            granted.add(WORLD_UNLOCKS[item_name])

    return granted


def vehicle_pickup_protection_active(ctx: MarbleBalanceContext) -> bool:
    stage = current_stage(ctx.slot_data)
    if stage is None or not in_level_active(ctx.slot_data):
        return False
    return (stage.get("difficulty"), stage.get("world"), stage.get("level")) in BONUS_VEHICLE_PICKUP_LEVELS


def physically_granted_normal_worlds(ctx: MarbleBalanceContext) -> set[tuple[str, str]]:
    granted = granted_normal_worlds(ctx)
    if not ctx.slot_data.get("options", {}).get("split_vehicle_world_access", True):
        return granted

    physical: set[tuple[str, str]] = set()
    received = set(received_item_names(ctx))
    for difficulty, world in granted:
        if difficulty == "Hard":
            physical.add((difficulty, world))
        elif world == "W5" and item_names.SUBMARINE not in received:
            continue
        elif world == "W6" and item_names.ROCKET_SHIP not in received:
            continue
        else:
            physical.add((difficulty, world))
    return physical


def apply_starting_access(slot_data: dict[str, Any]) -> None:
    for difficulty, world in slot_data.get("starting_worlds", {}).items():
        levels = range(1, 6)
        unlock_matching_levels(slot_data, difficulty, world, levels)


def sync_normal_world_access(ctx: MarbleBalanceContext) -> None:
    granted = physically_granted_normal_worlds(ctx)
    protect_vehicle_pickups = vehicle_pickup_protection_active(ctx)
    for difficulty in ctx.slot_data.get("enabled_difficulties", []):
        for world in NORMAL_WORLDS:
            if protect_vehicle_pickups and difficulty == "Normal" and world in {"W5", "W6"}:
                set_matching_levels(ctx.slot_data, difficulty, world, range(1, LEVELS_PER_WORLD[world] + 1), 0)
                continue
            if (difficulty, world) not in granted:
                set_matching_levels(ctx.slot_data, difficulty, world, range(1, LEVELS_PER_WORLD[world] + 1), 0)
                continue
            set_matching_levels(ctx.slot_data, difficulty, world, range(1, 6), 1)
            if world == "W7":
                late_value = 1 if completed_opening_levels(ctx, difficulty, world, "goal") >= 3 else 0
                set_matching_levels(ctx.slot_data, difficulty, world, range(6, LEVELS_PER_WORLD[world] + 1), late_value)


def sync_vehicle_access(ctx: MarbleBalanceContext) -> None:
    granted = granted_normal_worlds(ctx)
    received = set(received_item_names(ctx))
    split_vehicle_access = ctx.slot_data.get("options", {}).get("split_vehicle_world_access", True)
    protect_vehicle_pickups = vehicle_pickup_protection_active(ctx)

    for difficulty, flags in ctx.slot_data.get("vehicle_flags", {}).items():
        if difficulty not in ctx.slot_data.get("enabled_difficulties", []):
            continue
        submarine_allowed = (difficulty, "W5") in granted
        rocket_allowed = (difficulty, "W6") in granted
        if split_vehicle_access:
            submarine_allowed = submarine_allowed and item_names.SUBMARINE in received
            rocket_allowed = rocket_allowed and item_names.ROCKET_SHIP in received
        if protect_vehicle_pickups and difficulty == "Normal":
            submarine_allowed = False
            rocket_allowed = False
        write_u8_if_changed(flags.get(item_names.SUBMARINE), 1 if submarine_allowed else 0)
        write_u8_if_changed(flags.get(item_names.ROCKET_SHIP), 1 if rocket_allowed else 0)


def suppress_l11_world_unlock_side_effects(ctx: MarbleBalanceContext) -> None:
    granted = granted_normal_worlds(ctx)
    stage = current_stage(ctx.slot_data)
    current_identity = stage_identity(stage) if in_level_active(ctx.slot_data) else None

    for difficulty in ctx.slot_data.get("enabled_difficulties", []):
        for index, world in enumerate(NORMAL_WORLDS[:-1]):
            if LEVELS_PER_WORLD[world] < 11:
                continue

            if current_identity != ("stage", difficulty, world, 11):
                force_matching_level_states(ctx.slot_data, difficulty, world, range(11, 12), {1, 3}, 2)

            next_world = NORMAL_WORLDS[index + 1]
            if (difficulty, next_world) not in granted:
                force_matching_level_states(ctx.slot_data, difficulty, next_world, range(1, 6), {1, 2, 3}, 0)


def owned_bonus_worlds(ctx: MarbleBalanceContext) -> set[tuple[str, str]]:
    owned: set[tuple[str, str]] = {
        (difficulty, world)
        for difficulty, world in ctx.slot_data.get("starting_worlds", {}).items()
        if world in BONUS_WORLDS
    }
    for item_name in received_item_names(ctx):
        unlock = WORLD_UNLOCKS.get(item_name)
        if unlock and unlock[1] in BONUS_WORLDS:
            owned.add(unlock)
    return owned


def completed_opening_levels(ctx: MarbleBalanceContext, difficulty: str, world: str, category: str) -> int:
    completed = 0
    for location in ctx.slot_data.get("locations", {}).values():
        if (
            location.get("category") == category
            and location.get("difficulty") == difficulty
            and location.get("world") == world
            and location.get("level") in range(1, 6)
        ):
            address = (location.get("addresses") or {}).get("state")
            if address is not None and read_u8(address) == 3:
                completed += 1
    return completed


def owned_bonus_levels(ctx: MarbleBalanceContext) -> set[tuple[str, str, int]]:
    owned: set[tuple[str, str, int]] = set()
    for difficulty, world in owned_bonus_worlds(ctx):
        for level in range(1, 6):
            owned.add((difficulty, world, level))
        if completed_opening_levels(ctx, difficulty, world, "bonus_goal") >= 3:
            for level in range(6, LEVELS_PER_WORLD[world] + 1):
                owned.add((difficulty, world, level))
    return owned


def sync_bonus_vehicle_gates(ctx: MarbleBalanceContext) -> None:
    static = ctx.slot_data.get("static_addresses", {})
    if vehicle_pickup_protection_active(ctx):
        for difficulty, address_key in (("Easy", "easy_vehicle_gate"), ("Normal", "normal_vehicle_gate")):
            if difficulty in ctx.slot_data.get("enabled_difficulties", []):
                write_u8_if_changed(static.get(address_key), 15)
        return

    normal_owned_worlds = {world for difficulty, world in owned_bonus_worlds(ctx) if difficulty == "Normal"}
    submarine_side = bool(normal_owned_worlds)
    rocket_side = any(world in normal_owned_worlds for world in ("WB", "WC"))
    value = 15
    if submarine_side and rocket_side:
        value = 95
    elif submarine_side:
        value = 31
    elif rocket_side:
        value = 79

    for difficulty, address_key in (("Easy", "easy_vehicle_gate"), ("Normal", "normal_vehicle_gate")):
        if difficulty in ctx.slot_data.get("enabled_difficulties", []):
            write_u8_if_changed(static.get(address_key), value)


def sync_bonus_level_access(ctx: MarbleBalanceContext) -> None:
    owned = owned_bonus_levels(ctx)
    current = stage_identity(current_stage(ctx.slot_data)) if in_level_active(ctx.slot_data) else None
    for location in ctx.slot_data.get("locations", {}).values():
        if location.get("category") != "bonus_goal":
            continue
        key = (location.get("difficulty"), location.get("world"), location.get("level"))
        address = (location.get("addresses") or {}).get("state")
        if address is None:
            continue

        value = read_u8(address)
        if key in owned:
            if value == 0:
                write_u8(address, 1)
        elif current != ("stage", key[0], key[1], key[2]) and value in {1, 2, 3}:
            write_u8(address, 0)


def sync_mirror_trophies(ctx: MarbleBalanceContext) -> None:
    seen: set[tuple[int, int]] = set()
    for location in ctx.slot_data.get("locations", {}).values():
        addresses = location.get("addresses") or {}
        trophy = addresses.get("trophy")
        mirror_trophy = addresses.get("mirror_trophy")
        if trophy is None or mirror_trophy is None or (trophy, mirror_trophy) in seen:
            continue
        seen.add((trophy, mirror_trophy))
        normal_value = read_u8(trophy)
        mirror_value = read_u8(mirror_trophy)
        best = max(normal_value, mirror_value)
        if best and normal_value != best:
            write_u8(trophy, best)
        if best and mirror_value != best:
            write_u8(mirror_trophy, best)


def sync_junk_inventory(ctx: MarbleBalanceContext) -> None:
    received = received_item_names(ctx)
    live_junk_flags = ctx.slot_data.get("junk_live_flags", {})
    saved_junk_flags = ctx.slot_data.get("junk_saved_flags", {})
    unlock_junk_flags = ctx.slot_data.get("junk_unlock_flags", {})

    for junk_name in set(live_junk_flags) | set(saved_junk_flags) | set(unlock_junk_flags):
        count = min(99, received.count(junk_name))
        write_u8_if_changed(live_junk_flags.get(junk_name), count)
        write_u8_if_changed(saved_junk_flags.get(junk_name), count)
        write_u8_if_changed(unlock_junk_flags.get(junk_name), 1 if count else 0)


def hard_mode_option(slot_data: dict[str, Any]) -> str | int:
    return slot_data.get("options", {}).get("hard_mode_unlock", "item")


def sync_hard_mode_access(ctx: MarbleBalanceContext) -> None:
    hard_mode_flag = ctx.slot_data.get("static_addresses", {}).get("hard_mode_flag")
    if hard_mode_flag is None:
        return

    option = hard_mode_option(ctx.slot_data)
    if option in {"vanilla", 3}:
        return

    allowed = option in {"start", 0} or item_names.HARD_MODE in received_item_names(ctx)
    write_u8_if_changed(hard_mode_flag, 1 if allowed else 0)


def enforce_marble_access(ctx: MarbleBalanceContext) -> None:
    slot_data = ctx.slot_data
    static = slot_data.get("static_addresses", {})
    marble_flags = slot_data.get("marble_unlock_flags", {})
    received = set(received_item_names(ctx))
    allowed = {slot_data.get("starting_marble")}
    allowed.update(name for name in received if name in marble_flags)
    in_stage = in_level_active(slot_data)

    for name, address in marble_flags.items():
        if name in allowed:
            ensure_u8(address, 2 if name == slot_data.get("starting_marble") else 1)
        elif in_stage:
            write_u8_if_changed(address, 2)
        elif read_u8(address) != 0:
            write_u8(address, 0)

    current_marble = static.get("current_marble")
    if current_marble is not None:
        if in_stage:
            write_u8_if_changed(current_marble, 2)
            return
        current_index = read_u8(current_marble)
        if 0 <= current_index < len(MARBLES) and MARBLES[current_index] not in allowed:
            for index, name in enumerate(MARBLES):
                if name in allowed:
                    write_u8(current_marble, index)
                    break


def handle_traps(ctx: MarbleBalanceContext) -> None:  # noqa: C901
    static = ctx.slot_data.get("static_addresses", {})
    now = time.monotonic()
    stage = current_stage(ctx.slot_data)
    identity = stage_identity(stage)
    mirror_address = static.get("mirror_active_slot")
    blackout_address = static.get("blackout_trap_flag")
    noclip_address = static.get("noclip_trap_flag")
    inside_stage = stage is not None and in_level_active(ctx.slot_data)
    safe_gameplay = trap_safe_gameplay(ctx, stage)

    if blackout_address is not None:
        if ctx.blackout_active and goal_or_result_active(ctx.slot_data):
            if ctx.blackout_remaining > 0:
                ctx.blackout_delay_next_stage = True
                ctx.blackout_remaining = BLACKOUT_TRAP_DURATION
                logger.debug(
                    "Blackout Trap hit goal/result immediately after activation; "
                    "re-queued until the next countdown finishes."
                )
            else:
                ctx.blackout_owned = False
                ctx.blackout_remaining = 0.0
            logger.debug(f"Blackout Trap cleared: writing 0x{blackout_address:08X}=1.")
            write_u8_if_changed(blackout_address, 1)
            ctx.blackout_active = False
            ctx.blackout_started = False
            ctx.blackout_last_tick = now
            return

        blackout_ready = safe_gameplay
        if ctx.blackout_owned and blackout_ready and ctx.blackout_remaining > 0:
            elapsed = now - ctx.blackout_last_tick
            ctx.blackout_remaining = max(0.0, ctx.blackout_remaining - elapsed)
            ctx.blackout_last_tick = now
            if not ctx.blackout_active:
                logger.debug(
                    f"Blackout Trap active: writing 0x{blackout_address:08X}=2 "
                    f"for {ctx.blackout_remaining:.1f}s active gameplay."
                )
                ctx.blackout_active_since = now
                ctx.blackout_next_log_at = now + 1.0
                write_u8_if_changed(blackout_address, 2)
                ctx.blackout_started = True
            if now >= ctx.blackout_next_log_at:
                logger.debug(
                    f"Blackout Trap tick: writing 0x{blackout_address:08X}=3; "
                    f"{ctx.blackout_remaining:.1f}s remaining."
                )
                write_u8(blackout_address, 3)
                ctx.blackout_next_log_at = now + 1.0
            ctx.blackout_active = True
            ctx.blackout_delay_next_stage = False
        else:
            ctx.blackout_last_tick = now
            if ctx.blackout_active and inside_stage and read_u8(blackout_address) in {2, 3}:
                logger.debug(f"Blackout Trap cleared: writing 0x{blackout_address:08X}=1.")
                write_u8(blackout_address, 1)
            if ctx.blackout_remaining <= 0:
                ctx.blackout_owned = False
                ctx.blackout_active = False
                ctx.blackout_started = False

    if mirror_address is not None:
        if ctx.mirror_trap_active and (
            not inside_stage
            or (ctx.mirror_active_stage is not None and identity != ctx.mirror_active_stage)
        ):
            logger.debug(f"Mirror Trap cleared after leaving mirrored level: writing 0x{mirror_address:08X}=0.")
            write_u8_if_changed(mirror_address, 0)
            ctx.mirror_trap_active = False
            ctx.mirror_active_stage = None
            ctx.mirror_skip_stage = None

        if ctx.mirror_trap_pending and not in_level_active(ctx.slot_data):
            if read_u8(mirror_address) != 1:
                logger.debug(f"Mirror Trap preparing next level: writing 0x{mirror_address:08X}=1.")
            write_u8_if_changed(mirror_address, 1)

        if ctx.mirror_trap_pending and inside_stage and identity != ctx.mirror_skip_stage:
            logger.debug(f"Mirror Trap active for this attempt: holding 0x{mirror_address:08X}=1 until level exit.")
            write_u8_if_changed(mirror_address, 1)
            ctx.mirror_trap_pending = False
            ctx.mirror_trap_active = True
            ctx.mirror_active_since = now
            ctx.mirror_active_stage = identity
            ctx.mirror_skip_stage = None

        inverse_ready = safe_gameplay
        if ctx.inverse_trap_pending and inverse_ready:
            inverse_value = 0 if ctx.mirror_trap_active else 1
            logger.debug(
                f"Inverse Trap active: writing 0x{mirror_address:08X}={inverse_value} "
                "for 30.0s active gameplay or until goal/result."
            )
            write_u8_if_changed(mirror_address, inverse_value)
            ctx.inverse_trap_pending = False
            ctx.inverse_trap_active = True
            ctx.inverse_delay_next_stage = False
            ctx.inverse_remaining = INVERSE_TRAP_DURATION
            ctx.inverse_last_tick = now
            ctx.inverse_active_since = now
            ctx.inverse_next_log_at = now

        if ctx.mirror_trap_active and inside_stage and not ctx.inverse_trap_active:
            write_u8_if_changed(mirror_address, 1)

        if ctx.inverse_trap_active and safe_gameplay and ctx.inverse_remaining > 0:
            elapsed = now - ctx.inverse_last_tick
            ctx.inverse_remaining = max(0.0, ctx.inverse_remaining - elapsed)
            ctx.inverse_last_tick = now
            inverse_value = 0 if ctx.mirror_trap_active else 1
            if now >= ctx.inverse_next_log_at:
                logger.debug(
                    f"Inverse Trap tick: writing 0x{mirror_address:08X}={inverse_value}; "
                    f"{ctx.inverse_remaining:.1f}s remaining."
                )
                write_u8(mirror_address, inverse_value)
                ctx.inverse_next_log_at = now + 1.0
            else:
                write_u8_if_changed(mirror_address, inverse_value)
        else:
            ctx.inverse_last_tick = now
            if ctx.inverse_trap_active:
                write_u8_if_changed(mirror_address, 1 if ctx.mirror_trap_active else 0)

        if ctx.inverse_trap_active and (goal_or_result_active(ctx.slot_data) or ctx.inverse_remaining <= 0):
            logger.debug(
                f"Inverse Trap cleared: writing 0x{mirror_address:08X}="
                f"{1 if ctx.mirror_trap_active else 0}."
            )
            write_u8_if_changed(mirror_address, 1 if ctx.mirror_trap_active else 0)
            ctx.inverse_trap_active = False
            ctx.inverse_remaining = 0.0
    if noclip_address is not None:
        if (
            ctx.noclip_rewrite_after_clear_until > now
            and not ctx.noclip_rewrite_after_clear_done
            and read_u8(noclip_address) == 1
            and now - ctx.noclip_last_forced_zero_at >= 1.0
        ):
            logger.debug(
                "Noclip Trap goal handoff: address returned to 1, "
                f"writing 0x{noclip_address:08X}=0 once more."
            )
            write_u8(noclip_address, 0)
            ctx.noclip_rewrite_after_clear_done = True
            ctx.noclip_rewrite_after_clear_until = 0.0
            ctx.noclip_owned = False
            ctx.noclip_active = False
            ctx.noclip_remaining = 0.0
            ctx.noclip_delay_next_stage = False
            ctx.noclip_skip_stage = None
            return
        if (
            ctx.noclip_rewrite_after_clear_until
            and ctx.noclip_rewrite_after_clear_until <= now
        ):
            ctx.noclip_rewrite_after_clear_until = 0.0
            ctx.noclip_rewrite_after_clear_done = False

        if ctx.noclip_active and goal_or_result_active(ctx.slot_data):
            if ctx.noclip_remaining > 0:
                ctx.noclip_delay_next_stage = True
                ctx.noclip_skip_stage = None
                ctx.noclip_remaining = NOCLIP_TRAP_DURATION
                logger.debug(
                    "Noclip Trap hit goal/result immediately after activation; "
                    "re-queued until the next countdown finishes."
                )
            else:
                ctx.noclip_owned = False
                ctx.noclip_remaining = 0.0
            logger.debug(f"Noclip Trap cleared: writing 0x{noclip_address:08X}=1.")
            write_u8_if_changed(noclip_address, 1)
            ctx.noclip_active = False
            ctx.noclip_last_tick = now
            return

        noclip_countdown_ready = (
            stage is not None
            and in_level_active(ctx.slot_data)
            and level_countdown_ready(ctx, stage)
        )
        noclip_ready = noclip_countdown_ready and (
            not ctx.noclip_delay_next_stage
            or ctx.noclip_skip_stage is None
            or identity != ctx.noclip_skip_stage
        )
        if ctx.noclip_owned and noclip_ready and ctx.noclip_remaining > 0:
            elapsed = now - ctx.noclip_last_tick
            ctx.noclip_remaining = max(0.0, ctx.noclip_remaining - elapsed)
            ctx.noclip_last_tick = now
            if not ctx.noclip_active:
                logger.debug(
                    f"Noclip Trap active: writing 0x{noclip_address:08X}=0 "
                    f"for {ctx.noclip_remaining:.1f}s active gameplay."
                )
                ctx.noclip_active_since = now
                ctx.noclip_next_log_at = now
            ctx.noclip_active = True
            ctx.noclip_delay_next_stage = False
            if now >= ctx.noclip_next_log_at:
                logger.debug(
                    f"Noclip Trap tick: writing 0x{noclip_address:08X}=0; "
                    f"{ctx.noclip_remaining:.1f}s remaining."
                )
                write_u8(noclip_address, 0)
                ctx.noclip_next_log_at = now + 1.0
            else:
                write_u8_if_changed(noclip_address, 0)
        else:
            ctx.noclip_last_tick = now
            if ctx.noclip_active and read_u8(noclip_address) == 0:
                logger.debug(f"Noclip Trap cleared: writing 0x{noclip_address:08X}=1.")
                write_u8(noclip_address, 1)
            if ctx.noclip_remaining <= 0:
                ctx.noclip_owned = False
                ctx.noclip_remaining = 0.0
                ctx.noclip_active = False


def apply_received_item(ctx: MarbleBalanceContext, item_name: str) -> None:  # noqa: C901
    slot_data = ctx.slot_data

    if item_name in {item_names.GREEN_GEM, item_names.STUMP_TEMPLE_PIECE, item_names.VICTORY}:
        if item_name == item_names.VICTORY and not ctx.finished_game:
            Utils.async_start(ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}]))
            ctx.finished_game = True
        return

    if item_name == item_names.HARD_MODE:
        sync_hard_mode_access(ctx)
        return

    if item_name == item_names.SUBMARINE:
        sync_vehicle_access(ctx)
        return

    if item_name == item_names.ROCKET_SHIP:
        sync_vehicle_access(ctx)
        return

    if item_name == "Mirror Trap":
        ctx.mirror_trap_pending = True
        ctx.mirror_skip_stage = (
            stage_identity(current_stage(slot_data))
            if in_level_active(slot_data)
            else None
        )
        logger.debug("Mirror Trap received: queued for the next level attempt.")
        return
    if item_name == "Blackout Trap":
        ctx.blackout_remaining += BLACKOUT_TRAP_DURATION
        ctx.blackout_last_tick = time.monotonic()
        ctx.blackout_owned = True
        ctx.blackout_delay_next_stage = not trap_safe_gameplay(ctx, current_stage(slot_data))
        logger.debug(
            "Blackout Trap received: "
            + (
                "queued until the countdown finishes."
                if ctx.blackout_delay_next_stage
                else "starts after the current countdown finishes."
            )
        )
        return
    if item_name == "Inverse Trap":
        ctx.inverse_trap_pending = True
        ctx.inverse_delay_next_stage = not trap_safe_gameplay(ctx, current_stage(slot_data))
        logger.debug(
            "Inverse Trap received: "
            + ("queued until the countdown finishes." if ctx.inverse_delay_next_stage else "starts now.")
        )
        return
    if item_name == "Noclip Trap":
        ctx.noclip_remaining += NOCLIP_TRAP_DURATION
        ctx.noclip_last_tick = time.monotonic()
        ctx.noclip_owned = True
        stage = current_stage(slot_data)
        ctx.noclip_delay_next_stage = not trap_safe_gameplay(ctx, stage)
        ctx.noclip_skip_stage = (
            stage_identity(stage)
            if ctx.noclip_delay_next_stage and in_level_active(slot_data)
            else None
        )
        logger.debug(
            "Noclip Trap received: "
            + ("queued until the countdown finishes." if ctx.noclip_delay_next_stage else "starts now.")
        )
        return

    live_junk_flags = slot_data.get("junk_live_flags", {})
    saved_junk_flags = slot_data.get("junk_saved_flags", {})
    unlock_junk_flags = slot_data.get("junk_unlock_flags", {})
    if item_name in live_junk_flags or item_name in saved_junk_flags or item_name in unlock_junk_flags:
        live_value = add_u8(live_junk_flags.get(item_name))
        saved_value = add_u8(saved_junk_flags.get(item_name))
        write_u8_if_changed(unlock_junk_flags.get(item_name), 1)
        logger.debug(
            f"Junk item received: {item_name}; "
            f"live={live_value if live_value is not None else 'n/a'}, "
            f"saved={saved_value if saved_value is not None else 'n/a'}, "
            f"unlock={hex(unlock_junk_flags[item_name]) if item_name in unlock_junk_flags else 'n/a'}."
        )
        return

    if item_name in WORLD_UNLOCKS:
        difficulty, world = WORLD_UNLOCKS[item_name]
        if world in BONUS_WORLDS:
            unlock_matching_levels(slot_data, difficulty, world, range(1, 6))
        elif (difficulty, world) in physically_granted_normal_worlds(ctx):
            unlock_matching_levels(slot_data, difficulty, world, range(1, 6))
        return

    marble_flags = slot_data.get("marble_unlock_flags", {})
    if item_name in marble_flags:
        write_u8_if_changed(
            marble_flags[item_name],
            2 if item_name == slot_data.get("starting_marble") else 1,
        )
        return

    for flag_map_name in (
        "figure_roller_head_unlock_flags",
        "vehicle_part_flags",
    ):
        flag_map = slot_data.get(flag_map_name, {})
        if item_name in flag_map:
            ensure_u8(flag_map[item_name], 1)
            return

    if item_name not in ctx._logged_unsupported_items:
        logger.debug(f"No RAM write handler for received item: {item_name}")
        ctx._logged_unsupported_items.add(item_name)


async def process_received_items(ctx: MarbleBalanceContext) -> None:
    if not ctx.slot_data or ctx.slot is None:
        return

    if ctx._skip_existing_received_items:
        while ctx.processed_item_count < len(ctx.items_received):
            network_item = ctx.items_received[ctx.processed_item_count]
            ctx.processed_item_count += 1
            item_name = item_name_from_network(ctx, network_item.item)
            if item_name and item_name not in TRAPS:
                apply_received_item(ctx, item_name)
        ctx._skip_existing_received_items = False
        return

    while ctx.processed_item_count < len(ctx.items_received):
        network_item = ctx.items_received[ctx.processed_item_count]
        ctx.processed_item_count += 1
        item_name = item_name_from_network(ctx, network_item.item)
        if item_name:
            apply_received_item(ctx, item_name)


async def dolphin_sync_task(ctx: MarbleBalanceContext) -> None:
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
                if dolphin_memory_engine.read_bytes(GAME_ID_ADDRESS, len(GAME_ID)) != GAME_ID:
                    dolphin_memory_engine.un_hook()
                    ctx.dolphin_status = CONNECTION_LOST_STATUS
                    sleep_time = 2
                    continue
                if ctx.slot_data:
                    apply_starting_access(ctx.slot_data)
                    sync_bonus_vehicle_gates(ctx)
                    await process_received_items(ctx)
                    sync_hard_mode_access(ctx)
                    sync_vehicle_access(ctx)
                    sync_normal_world_access(ctx)
                    suppress_l11_world_unlock_side_effects(ctx)
                    sync_bonus_vehicle_gates(ctx)
                    sync_bonus_level_access(ctx)
                    sync_mirror_trophies(ctx)
                    sync_junk_inventory(ctx)
                    enforce_marble_access(ctx)
                    handle_traps(ctx)
                    sync_save_slot_guard(ctx)
                    await check_locations(ctx)
                sleep_time = 0.1
                continue

            if ctx.dolphin_status == CONNECTION_CONNECTED_STATUS:
                logger.info("Connection to Dolphin lost, reconnecting...")
            ctx.dolphin_status = CONNECTION_LOST_STATUS
            logger.info("Attempting to connect to Dolphin...")
            dolphin_memory_engine.hook()
            if not dolphin_memory_engine.is_hooked():
                sleep_time = 5
                continue

            if dolphin_memory_engine.read_bytes(GAME_ID_ADDRESS, len(GAME_ID)) != GAME_ID:
                logger.info(CONNECTION_REFUSED_GAME_STATUS)
                ctx.dolphin_status = CONNECTION_REFUSED_GAME_STATUS
                dolphin_memory_engine.un_hook()
                sleep_time = 5
                continue

            ctx.dolphin_status = CONNECTION_CONNECTED_STATUS
            logger.info(CONNECTION_CONNECTED_STATUS)
        except Exception:
            dolphin_memory_engine.un_hook()
            ctx.dolphin_status = CONNECTION_LOST_STATUS
            logger.error(traceback.format_exc())
            sleep_time = 5


async def main(args: Namespace) -> None:
    ctx = MarbleBalanceContext(args.connect, args.password, args.patch_file)
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
    parser = get_base_parser(description="Marbles! Balance Challenge Archipelago Client")
    parser.add_argument("--name", default=None, help="Slot Name to connect as.")
    parser.add_argument("url", nargs="?", help="Archipelago connection url or .apmbc output file")
    parsed_args = parser.parse_args(args)
    if parsed_args.url and str(parsed_args.url).endswith(".apmbc"):
        parsed_args.patch_file = parsed_args.url
        parsed_args.url = None
    else:
        parsed_args.patch_file = None
        parsed_args = handle_url_arg(parsed_args, parser=parser)
    Utils.init_logging("MarbleBalanceClient", exception_logger="Client")
    asyncio.run(main(parsed_args))


if __name__ == "__main__":
    launch(*sys.argv[1:])
