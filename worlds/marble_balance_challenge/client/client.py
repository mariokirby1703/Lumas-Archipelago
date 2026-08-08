from __future__ import annotations

import asyncio
import json
import sys
import traceback
from argparse import Namespace
from pathlib import Path
from typing import Any

import ModuleUpdate
import Utils
from CommonClient import ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, handle_url_arg, logger, server_loop
from NetUtils import ClientStatus

from ..Names import item_names
from ..world_constants import BONUS_WORLDS, DIFFICULTIES, GAME_NAME, LEVELS_PER_WORLD, NORMAL_WORLDS

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

        if patch_file:
            self.load_patch_file(patch_file)

    def load_patch_file(self, patch_file: str) -> None:
        path = Path(patch_file)
        with path.open("r", encoding="utf-8") as file:
            self.patch_data = json.load(file)
        self.slot_data = self.patch_data.get("slot_data", {})
        self.auth = self.slot_data.get("player_name") or self.auth
        logger.info(f"Loaded {path.name}.")

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
            self.locations_checked = set()
            logger.info("Connected to Archipelago as Marbles! Balance Challenge.")

    async def disconnect(self, allow_autoreconnect: bool = False) -> None:
        self.slot_data = self.patch_data.get("slot_data", {})
        self.processed_item_count = 0
        self._logged_unsupported_items.clear()
        await super().disconnect(allow_autoreconnect)

    def make_gui(self):
        ui = super().make_gui()
        ui.base_title = "Archipelago Marbles! Balance Challenge Client"
        return ui


def read_u8(address: int) -> int:
    import dolphin_memory_engine

    return dolphin_memory_engine.read_byte(address)


def write_u8(address: int, value: int) -> None:
    import dolphin_memory_engine

    dolphin_memory_engine.write_byte(address, value & 0xFF)


def ensure_u8(address: int | None, value: int = 1) -> None:
    if address is not None and read_u8(address) < value:
        write_u8(address, value)


def current_level_identity(slot_data: dict[str, Any]) -> tuple[str | None, str | None, int | None]:
    static = slot_data.get("static_addresses", {})
    try:
        world_index = read_u8(static["current_world_or_mode_index"])
        stage_index = read_u8(static["selected_stage_index"])
        difficulty_index = read_u8(static["difficulty_a"])
    except Exception:
        return None, None, None

    world_lookup = {index: world for index, world in enumerate((*NORMAL_WORLDS, *BONUS_WORLDS))}
    difficulty_lookup = {value: name for name, value in DIFFICULTY_INDEX.items()}
    return difficulty_lookup.get(difficulty_index), world_lookup.get(world_index), stage_index + 1


def is_current_location(location: dict[str, Any], slot_data: dict[str, Any]) -> bool:
    difficulty, world, level = current_level_identity(slot_data)
    return (
        location.get("difficulty") == difficulty
        and location.get("world") == world
        and location.get("level") == level
    )


def location_is_checked(location: dict[str, Any], slot_data: dict[str, Any]) -> bool:
    category = location.get("category")
    addresses = location.get("addresses") or {}

    if category == "balance_board":
        static = slot_data.get("static_addresses", {})
        safety = slot_data.get("safety", {})
        try:
            return (
                read_u8(static["current_world_or_mode_index"]) == safety.get("balance_board_world_or_mode_index", 14)
                and read_u8(static["selected_stage_index"]) == location.get("level", 0) - 1
                and read_u8(static["stage_cleared_flag"]) in safety.get("stage_cleared_values", [94, 95])
            )
        except Exception:
            return False

    if category in {"goal", "bonus_goal"}:
        state = addresses.get("state")
        return state is not None and read_u8(state) >= 3

    if category in TROPHY_REQUIREMENTS:
        trophy = addresses.get("trophy")
        return trophy is not None and read_u8(trophy) >= TROPHY_REQUIREMENTS[category]

    if category in {"green_gem", "stump_piece"}:
        address = addresses.get(category)
        return address is not None and read_u8(address) > 0

    if category == "ant":
        ant = addresses.get("ant")
        if ant is not None and read_u8(ant) > 0:
            return True
        temporary_pickup = addresses.get("temporary_pickup")
        return (
            temporary_pickup is not None
            and read_u8(temporary_pickup) > 0
            and is_current_location(location, slot_data)
        )

    return False


async def check_locations(ctx: MarbleBalanceContext) -> None:
    if not ctx.slot_data:
        return

    newly_checked: set[int] = set()
    for location_name, location in ctx.slot_data.get("locations", {}).items():
        location_id = location.get("id")
        if not location_id or location_id in ctx.locations_checked:
            continue
        try:
            if location_is_checked(location, ctx.slot_data):
                ctx.locations_checked.add(location_id)
                newly_checked.add(location_id)
                logger.info(f"Checked: {location_name}")
        except Exception:
            logger.debug("Failed to read location %s.", location_name, exc_info=True)

    if newly_checked and ctx.slot is not None:
        await ctx.send_msgs([{"cmd": "LocationChecks", "locations": list(newly_checked)}])


def item_name_from_network(ctx: MarbleBalanceContext, item_id: int) -> str | None:
    try:
        return ctx.item_names.lookup_in_game(item_id, ctx.game)
    except Exception:
        return None


def normal_world_unlocks() -> dict[str, tuple[str, str]]:
    return {
        item_names.world_access_name(difficulty, world): (difficulty, world)
        for difficulty in DIFFICULTIES
        for world in NORMAL_WORLDS
    }


def bonus_level_unlocks() -> dict[str, tuple[str, str, int]]:
    unlocks: dict[str, tuple[str, str, int]] = {}
    for difficulty in ("Normal", "Hard"):
        for world in BONUS_WORLDS:
            for level in range(1, LEVELS_PER_WORLD[world] + 1):
                unlocks[item_names.bonus_level_unlock_name(difficulty, world, level)] = (difficulty, world, level)
    return unlocks


WORLD_UNLOCKS = normal_world_unlocks()
BONUS_UNLOCKS = bonus_level_unlocks()


def unlock_matching_levels(slot_data: dict[str, Any], difficulty: str, world: str, levels: range) -> None:
    for location in slot_data.get("locations", {}).values():
        if (
            location.get("category") in {"goal", "bonus_goal"}
            and location.get("difficulty") == difficulty
            and location.get("world") == world
            and location.get("level") in levels
        ):
            ensure_u8((location.get("addresses") or {}).get("state"), 1)


def set_matching_levels(slot_data: dict[str, Any], difficulty: str, world: str, levels: range, value: int) -> None:
    for location in slot_data.get("locations", {}).values():
        if (
            location.get("category") == "goal"
            and location.get("difficulty") == difficulty
            and location.get("world") == world
            and location.get("level") in levels
        ):
            address = (location.get("addresses") or {}).get("state")
            if address is not None and read_u8(address) != value:
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
    return "Hard" if goal in {"hard_w7_l10", 1} else "Normal"


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

    required_stump_pieces = slot_data.get("options", {}).get("required_stump_pieces_for_w7", 60)
    if item_names_received.count(item_names.STUMP_TEMPLE_PIECE) >= required_stump_pieces:
        granted.add((goal_difficulty(slot_data), "W7"))

    return granted


def apply_starting_access(slot_data: dict[str, Any]) -> None:
    for difficulty, world in slot_data.get("starting_worlds", {}).items():
        levels = range(1, 6)
        unlock_matching_levels(slot_data, difficulty, world, levels)


def sync_normal_world_access(ctx: MarbleBalanceContext) -> None:
    granted = granted_normal_worlds(ctx)
    for difficulty in ctx.slot_data.get("enabled_difficulties", []):
        for world in NORMAL_WORLDS:
            if (difficulty, world) in granted:
                set_matching_levels(ctx.slot_data, difficulty, world, range(1, 6), 1)
            else:
                set_matching_levels(ctx.slot_data, difficulty, world, range(1, LEVELS_PER_WORLD[world] + 1), 0)


def apply_received_item(ctx: MarbleBalanceContext, item_name: str) -> None:
    slot_data = ctx.slot_data

    if item_name in {item_names.GREEN_GEM, item_names.STUMP_TEMPLE_PIECE, item_names.VICTORY}:
        if item_name == item_names.VICTORY and not ctx.finished_game:
            Utils.async_start(ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}]))
            ctx.finished_game = True
        return

    static = slot_data.get("static_addresses", {})
    if item_name == item_names.HARD_MODE:
        ensure_u8(static.get("hard_mode_flag"), 1)
        return

    if item_name == item_names.SUBMARINE:
        for flags in slot_data.get("vehicle_flags", {}).values():
            ensure_u8(flags.get(item_names.SUBMARINE), 1)
        return

    if item_name == item_names.ROCKET_SHIP:
        for flags in slot_data.get("vehicle_flags", {}).values():
            ensure_u8(flags.get(item_names.ROCKET_SHIP), 1)
        return

    if item_name in WORLD_UNLOCKS:
        difficulty, world = WORLD_UNLOCKS[item_name]
        unlock_matching_levels(slot_data, difficulty, world, range(1, 6))
        return

    if item_name in BONUS_UNLOCKS:
        difficulty, world, level = BONUS_UNLOCKS[item_name]
        unlock_matching_levels(slot_data, difficulty, world, range(level, level + 1))
        return

    for flag_map_name in (
        "marble_unlock_flags",
        "figure_roller_head_unlock_flags",
        "junk_live_flags",
        "junk_saved_flags",
        "vehicle_part_flags",
        "recipe_unlock_flags",
    ):
        flag_map = slot_data.get(flag_map_name, {})
        if item_name in flag_map:
            ensure_u8(flag_map[item_name], 1)
            return

    if item_name == item_names.JUNK_FACTORY_ACCESS:
        if item_name not in ctx._logged_unsupported_items:
            logger.warning("Junk Factory Access receive logic still needs safe Anthony's House gating addresses.")
            ctx._logged_unsupported_items.add(item_name)
        return

    if item_name not in ctx._logged_unsupported_items:
        logger.info(f"No RAM write handler for received item: {item_name}")
        ctx._logged_unsupported_items.add(item_name)


async def process_received_items(ctx: MarbleBalanceContext) -> None:
    if not ctx.slot_data or ctx.slot is None:
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
                if ctx.slot_data:
                    apply_starting_access(ctx.slot_data)
                    await process_received_items(ctx)
                    sync_normal_world_access(ctx)
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
            await ctx.disconnect(allow_autoreconnect=True)
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
