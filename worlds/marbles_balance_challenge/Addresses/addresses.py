from __future__ import annotations

from ..world_constants import FIGURE_ROLLER_HEADS, JUNK_ITEMS, MARBLES, WORLD_INDEX

CURRENT_WORLD_OR_MODE_INDEX = 0x8049D945
SELECTED_STAGE_INDEX = 0x8049D94D
DIFFICULTY_A = 0x8049D95D
DIFFICULTY_B = 0x804E0DF8
SELECTED_SAVE_SLOT = 0x8049D99F
CURRENT_GAME_MODE = 0x8049D96F
CURRENT_HUB_SCREEN = 0x804E612F
IN_GAME_INDICATOR = 0x804881AF
STAGE_CLEARED_FLAG = 0x8048D1B5
MIRROR_ACTIVE_SLOT = 0x8049D96B
BLACKOUT_TRAP_FLAG = 0x80490A42
NOCLIP_TRAP_FLAG = 0x80CBD6EB
PAL_WORLD_MAP_STAGE_ID = 0x80474B2E
PAL_FREE_MODE_STAGE_ID = 0x80474ACB
PAL_STAGE_CRYSTAL_COUNT = 0x8079CC40
GREEN_OR_ANT_TEMPORARY_PICKUP = 0x804E10BF
STUMP_TEMPORARY_PICKUP = 0x804E10B9
JUNK_TEMPORARY_PICKUP = 0x804E10B8
ANTHONY_TEMPORARY_PICKUP = GREEN_OR_ANT_TEMPORARY_PICKUP
CURRENT_MARBLE = 0x804E6187

HARD_MODE_FLAG = 0x804DF5F4
EASY_SUBMARINE_FLAG = 0x804DF550
EASY_ROCKET_SHIP_FLAG = 0x804DF551
NORMAL_SUBMARINE_FLAG = 0x804DF57F
NORMAL_ROCKET_SHIP_FLAG = 0x804DF580
EASY_VEHICLE_GATE = 0x804DF903
NORMAL_VEHICLE_GATE = 0x804DF908

MARBLE_UNLOCK_FLAGS = {name: 0x804DF36E + index for index, name in enumerate(MARBLES)}
FIGURE_ROLLER_HEAD_UNLOCK_FLAGS = {name: 0x804DF521 + index for index, name in enumerate(FIGURE_ROLLER_HEADS)}

JUNK_LIVE_FLAGS = {name: 0x804DF4A2 + index for index, name in enumerate(JUNK_ITEMS)}
JUNK_SAVED_FLAGS = {name: 0x9046F74E + index for index, name in enumerate(JUNK_ITEMS)}
JUNK_UNLOCK_FLAGS = {name: 0x804DF445 + index for index, name in enumerate(JUNK_ITEMS)}

VEHICLE_PART_FLAGS = {
    "Can": 0x804DF4BB,
    "Periscope": 0x804DF4BC,
    "Screw": 0x804DF4BD,
    "Rocket Engine": 0x804DF4BE,
    "Wing": 0x804DF4BF,
}

DIFFICULTY_TROPHY_ANCHORS = {
    "Easy": 0x804CA790,
    "Normal": 0x804CDB4C,
    "Hard": 0x804D0F08,
}

DIFFICULTY_MIRROR_TROPHY_ANCHORS = {
    "Easy": 0x804CA7E0,
    "Normal": 0x804CDB9C,
    "Hard": 0x804D0F58,
}

BONUS_TROPHY_ANCHORS = {
    "Normal": {
        "WA": 0x804D42C4,
        "WB": 0x804D497C,
        "WC": 0x804D56EC,
    },
    "Hard": {
        "WA": 0x804D645C,
        "WB": 0x804D5034,
        "WC": 0x804D5DA4,
    },
}


def normal_level_record(difficulty: str, world: str, level: int) -> dict[str, int | None]:
    trophy = DIFFICULTY_TROPHY_ANCHORS[difficulty] + WORLD_INDEX[world] * 0x764 + (level - 1) * 0xAC
    mirror_trophy = DIFFICULTY_MIRROR_TROPHY_ANCHORS[difficulty] + WORLD_INDEX[world] * 0x764 + (level - 1) * 0xAC
    return {
        "state": trophy - 0x0C,
        "green_gem": trophy - 0x05,
        "stump_piece": None if world == "W7" else trophy - 0x01,
        "ant": trophy - 0x05 if difficulty == "Hard" and level <= 10 else None,
        "trophy": trophy,
        "mirror_trophy": mirror_trophy,
    }


def bonus_level_record(difficulty: str, world: str, level: int) -> dict[str, int | None]:
    anchor = BONUS_TROPHY_ANCHORS[difficulty][world]
    if anchor is None:
        return {"state": None, "stump_piece": None, "ant": None, "trophy": None}
    trophy = anchor + (level - 1) * 0xAC
    return {
        "state": trophy - 0x0C,
        "stump_piece": None,
        "ant": trophy - 0x05 if difficulty == "Hard" else None,
        "trophy": trophy,
    }


def stage_id(difficulty: str, world: str, level: int) -> int | None:
    if world not in WORLD_INDEX or world.startswith("W") and len(world) == 2 and world[1].isdigit() and world != "W7":
        pass
    if world not in ("W1", "W2", "W3", "W4", "W5", "W6", "W7"):
        return None
    world_base = {
        "W1": 0x01,
        "W2": 0x22,
        "W3": 0x43,
        "W4": 0x64,
        "W5": 0x85,
        "W6": 0xA6,
        "W7": 0xC7,
    }[world]
    difficulty_offset = {"Normal": 0, "Easy": 1, "Hard": 2}[difficulty]
    return world_base + (level - 1) * 3 + difficulty_offset


STATIC_ADDRESSES = {
    "current_world_or_mode_index": CURRENT_WORLD_OR_MODE_INDEX,
    "selected_stage_index": SELECTED_STAGE_INDEX,
    "difficulty_a": DIFFICULTY_A,
    "difficulty_b": DIFFICULTY_B,
    "selected_save_slot": SELECTED_SAVE_SLOT,
    "current_game_mode": CURRENT_GAME_MODE,
    "current_hub_screen": CURRENT_HUB_SCREEN,
    "in_game_indicator": IN_GAME_INDICATOR,
    "stage_cleared_flag": STAGE_CLEARED_FLAG,
    "mirror_active_slot": MIRROR_ACTIVE_SLOT,
    "blackout_trap_flag": BLACKOUT_TRAP_FLAG,
    "noclip_trap_flag": NOCLIP_TRAP_FLAG,
    "pal_world_map_stage_id": PAL_WORLD_MAP_STAGE_ID,
    "pal_free_mode_stage_id": PAL_FREE_MODE_STAGE_ID,
    "pal_stage_crystal_count": PAL_STAGE_CRYSTAL_COUNT,
    "green_or_ant_temporary_pickup": GREEN_OR_ANT_TEMPORARY_PICKUP,
    "stump_temporary_pickup": STUMP_TEMPORARY_PICKUP,
    "junk_temporary_pickup": JUNK_TEMPORARY_PICKUP,
    "anthony_temporary_pickup": ANTHONY_TEMPORARY_PICKUP,
    "current_marble": CURRENT_MARBLE,
    "hard_mode_flag": HARD_MODE_FLAG,
    "easy_submarine_flag": EASY_SUBMARINE_FLAG,
    "easy_rocket_ship_flag": EASY_ROCKET_SHIP_FLAG,
    "normal_submarine_flag": NORMAL_SUBMARINE_FLAG,
    "normal_rocket_ship_flag": NORMAL_ROCKET_SHIP_FLAG,
    "easy_vehicle_gate": EASY_VEHICLE_GATE,
    "normal_vehicle_gate": NORMAL_VEHICLE_GATE,
}

assert set(JUNK_LIVE_FLAGS) == set(JUNK_ITEMS)
assert set(JUNK_UNLOCK_FLAGS) == set(JUNK_ITEMS)
assert set(MARBLE_UNLOCK_FLAGS) == set(MARBLES)
assert set(FIGURE_ROLLER_HEAD_UNLOCK_FLAGS) == set(FIGURE_ROLLER_HEADS)
