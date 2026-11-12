"""Experimental read-only profile derived from static references and a live menu read.

Names hash to the exact 51-entry runtime table. Byte meanings remain under investigation.
This is not an item-write profile and must not enable randomized gameplay.
"""

ABILITY_NAMES = (
    "GrappleGun", "EnergyGun", "SuperBuild", "Parkour", "Grab", "TargetThrow", "FinishingMove", "Parry",
    "Scanner", "Map", "Camera", "Surveillance", "Wiretap", "DataScanner", "Snapshot", "Album", "Ellie",
    "Policestation", "Jetpack", "FireAxe", "Pigs", "FastTravel", "SF_Residential", "SF_Docks", "WI_Farmlands",
    "WI_Forest", "BR_Brooklyn_Bridge", "BR_Golden_Gate", "BR_Twin_Bridge", "IS_Liberty_Island", "IS_Prison_Island",
    "IS_Space_Centre", "NY_Airport", "NY_Beach", "NY_Canal", "NY_Central_Park", "NY_Chinatown", "NY_Downtown",
    "NY_Downtown_East", "NY_Downtown_West", "NY_Little_Italy", "NY_Times_Square", "NY_Tunnel", "NY_Uptown",
    "Unassigned District", "Bonus_Missions", "DisguiseBooth", "Race", "SuperStrength", "Act2", "2x_Brick_Multi",
)


def symbol_hash(name: str) -> int:
    """Uppercase FNV-1, distinct from the archive's name hash."""
    value = 0x811C9DC5
    for byte in name.upper().encode("ascii"):
        value = ((value * 0x1000193) ^ byte) & 0xFFFFFFFF
    return value


def validate_table(values: list[int]) -> None:
    if values != [symbol_hash(name) for name in ABILITY_NAMES]:
        raise ValueError("Runtime symbol table does not match the experimental profile")


def decode_ability_query(existing: list[int], pending: list[int]) -> dict[str, bool]:
    """Reproduce IsAbilityUnlocked's statically observed two-byte OR query."""
    if len(existing) != len(ABILITY_NAMES) or len(pending) != len(ABILITY_NAMES):
        raise ValueError("Incomplete ability arrays")
    if any(type(value) is not int or not 0 <= value <= 255 for value in existing + pending):
        raise ValueError("Invalid ability byte")
    return {name: bool(existing[index] or pending[index]) for index, name in enumerate(ABILITY_NAMES)}
