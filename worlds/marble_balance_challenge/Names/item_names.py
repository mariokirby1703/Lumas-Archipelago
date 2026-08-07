from ..world_constants import HARD_BONUS_WORLD_DISPLAY_NAMES, WORLD_DISPLAY_NAMES

GREEN_GEM = "Green Gem"
STUMP_TEMPLE_PIECE = "Stump Temple Piece"
HARD_MODE = "Hard Mode"
SUBMARINE = "Submarine"
ROCKET_SHIP = "Rocket Ship"
JUNK_FACTORY_ACCESS = "Junk Factory Access"
VICTORY = "Victory"


def world_access_name(difficulty: str, world: str) -> str:
    return f"{WORLD_DISPLAY_NAMES[world]} {difficulty} Unlock"


def bonus_level_unlock_name(difficulty: str, world: str, level: int) -> str:
    if difficulty == "Hard":
        return f"{HARD_BONUS_WORLD_DISPLAY_NAMES[world]} {level:02d} Hard Unlock"
    return f"{WORLD_DISPLAY_NAMES[world]} {level:02d} Unlock"


def marble_name(marble: str) -> str:
    return f"{marble}"


def head_name(head: str) -> str:
    return f"{head}"


def junk_name(junk: str) -> str:
    return junk


def vehicle_part_name(part: str) -> str:
    return f"{part}"


def recipe_name(recipe: str) -> str:
    return f"{recipe} Recipe"
