from ..world_constants import (
    HARD_BONUS_WORLD_DISPLAY_NAMES,
    WORLD_DISPLAY_NAMES,
)

GREEN_GEM = "Green Gem"
STUMP_TEMPLE_PIECE = "Stump Temple Piece"
HARD_MODE = "Hard Mode"
SUBMARINE = "Submarine"
ROCKET_SHIP = "Rocket Ship"
VICTORY = "Victory"


def world_access_name(difficulty: str, world: str) -> str:
    if world in HARD_BONUS_WORLD_DISPLAY_NAMES and difficulty == "Hard":
        return f"{HARD_BONUS_WORLD_DISPLAY_NAMES[world]} Hard Unlock"
    if world in HARD_BONUS_WORLD_DISPLAY_NAMES and difficulty == "Normal":
        return f"{WORLD_DISPLAY_NAMES[world]} Easy/Normal Unlock"
    return f"{WORLD_DISPLAY_NAMES[world]} {difficulty} Unlock"


def marble_name(marble: str) -> str:
    return f"{marble}"


def head_name(head: str) -> str:
    return f"{head}"


def junk_name(junk: str) -> str:
    return junk


def vehicle_part_name(part: str) -> str:
    return f"{part}"
