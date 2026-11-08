"""Disc-derived region profiles. The AP game name and network IDs stay shared."""
from __future__ import annotations

from typing import Any

PAL = "PAL"
NTSC_U = "NTSC-U"
GAME_IDS = {PAL: b"RK6P18", NTSC_U: b"RK6E18"}
GAME_TITLES = {PAL: "Marbles! Balance Challenge", NTSC_U: "Marble Saga: Kororinpa"}
BALANCE_BOARD_COUNTS = {PAL: 100, NTSC_U: 30}


def region_for_options(options: Any) -> str:
    return NTSC_U if options.game_region.value == 1 else PAL


def translate_address(address: int | None, region: str) -> int | None:
    """Translate only known PAL address families for the required Save Slot 3.

    Save stride: PAL 0x166B8, US 0x137A8 (70 * 0xAC + 8 padding).
    The selected slot is index 2. Inventory follows the shortened board array.
    Heap/MEM2 addresses cannot be translated from disc layout alone.
    """
    if address is None or region == PAL:
        return address
    if region != NTSC_U:
        raise ValueError(f"Unsupported disc region: {region}")
    if 0x80471600 <= address < 0x8049D9E4:
        return address - 0x5200
    if 0x804CA754 <= address < 0x804D7878:
        return address - 0xB020
    if 0x804DF36E <= address <= 0x804DF908:
        return address - 0xDF28
    if 0x804E0DF8 <= address < 0x806C6740:
        return address - 0xDF30
    return None


def translate_tree(value: Any, region: str) -> Any:
    if isinstance(value, dict):
        return {key: translate_tree(item, region) for key, item in value.items()}
    if isinstance(value, int):
        return translate_address(value, region)
    return value


def apply_region_profile(slot_data: dict[str, Any], region: str) -> dict[str, Any]:
    """Apply to freshly built PAL slot data, never to an already translated profile."""
    slot_data["disc_region"] = region
    slot_data["disc_game_id"] = GAME_IDS[region].decode("ascii")
    slot_data["disc_title"] = GAME_TITLES[region]
    slot_data["balance_board_level_count"] = BALANCE_BOARD_COUNTS[region]
    for key in ("static_addresses", "marble_unlock_flags", "figure_roller_head_unlock_flags",
                "junk_live_flags", "junk_saved_flags", "junk_unlock_flags", "vehicle_part_flags", "vehicle_flags"):
        slot_data[key] = translate_tree(slot_data[key], region)
    for location in slot_data["locations"].values():
        if "addresses" in location:
            location["addresses"] = translate_tree(location["addresses"], region)
    # These PAL-only heap/MEM2 probes have no verified US counterpart. The US
    # client uses the disc-mapped clear flag; experimental traps remain inactive.
    slot_data["safety"]["experimental_traps_supported"] = region == PAL
    return slot_data
