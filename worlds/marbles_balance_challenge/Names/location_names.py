from ..world_constants import (
    BONUS_WORLDS,
    HARD_BONUS_WORLD_DISPLAY_NAMES,
    WORLD_DISPLAY_NAMES,
)


def level_prefix(difficulty: str, world: str, level: int) -> str:
    return (
        f"{world_display_name(difficulty, world)} {level:02d} "
        f"{difficulty_display_name(difficulty, world)}"
    )


def difficulty_display_name(difficulty: str, world: str) -> str:
    if difficulty == "Normal" and world in BONUS_WORLDS:
        return "Easy/Normal"
    return difficulty


def world_display_name(difficulty: str, world: str) -> str:
    if difficulty == "Hard" and world in HARD_BONUS_WORLD_DISPLAY_NAMES:
        return HARD_BONUS_WORLD_DISPLAY_NAMES[world]
    return WORLD_DISPLAY_NAMES[world]


def goal_location_name(difficulty: str, world: str, level: int) -> str:
    return f"{level_prefix(difficulty, world, level)} Goal"


def trophy_location_name(difficulty: str, world: str, level: int, trophy: str) -> str:
    return f"{level_prefix(difficulty, world, level)} {trophy} Trophy"


def green_gem_location_name(difficulty: str, world: str, level: int) -> str:
    return f"{level_prefix(difficulty, world, level)} Green Gem"


def stump_piece_location_name(difficulty: str, world: str, level: int) -> str:
    return f"{level_prefix(difficulty, world, level)} Stump Temple Piece"


def ant_location_name(difficulty: str, world: str, level: int) -> str:
    return f"{level_prefix(difficulty, world, level)} Anthony"


def tutorial_location_name(index: int) -> str:
    return f"Tutorial {index:02d} Goal"


def balance_board_location_name(index: int) -> str:
    return f"Wii Balance Board {index} Goal"
