from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any

from .world_constants import HUB_WORLD_KEY, SPARK_ITEM_BY_AMOUNT
from .world_constants import WORLD_KEY_BY_NAME, WORLD_KEYS, WORLD_NAMES


@dataclass(frozen=True)
class ObjectData:
    name: str
    value: int
    unlockable: bool
    note: str = ""


@dataclass(frozen=True)
class ObjectRequirement:
    name: str
    selected_value: int
    global_value: int | None


@dataclass(frozen=True)
class ChallengeData:
    world_key: str | None
    world_name: str
    challenge: int
    challenge_type: str
    spark_reward: int
    special: str | None
    block_value: int | None
    objects: tuple[ObjectRequirement, ...]


@dataclass(frozen=True)
class PossibleChallengeRequirement:
    objects: tuple[str, ...]
    max_spark: int | None = None


def _load_json(filename: str) -> Any:
    path = files(__package__).joinpath("data", filename)
    return json.loads(path.read_text(encoding="utf-8"))


def _world_key(world_label: str) -> str | None:
    if world_label == "Hub World":
        return HUB_WORLD_KEY
    match = re.match(r"World\s+(\d+)\s+\((.+)\)", world_label)
    if not match:
        raise ValueError(f"Unrecognized Create world label: {world_label!r}")
    number = int(match.group(1))
    key = f"W{number:02d}"
    expected_name = WORLD_NAMES[key]
    parsed_name = match.group(2)
    if parsed_name != expected_name:
        raise ValueError(f"World label mismatch for {key}: {parsed_name!r} != {expected_name!r}")
    return key


def _expand_object_range(value: str) -> range:
    start, end = value.split("-", 1)
    return range(int(start), int(end) + 1)


GLOBAL_OBJECT_DATA: tuple[ObjectData, ...] = tuple(
    ObjectData(
        name=entry["name"],
        value=int(entry["value"]),
        unlockable=bool(entry["unlockable"]),
        note=entry.get("note", ""),
    )
    for entry in _load_json("global_object_values.json")["objects"]
)
OBJECT_BY_VALUE = {obj.value: obj for obj in GLOBAL_OBJECT_DATA}
UNLOCKABLE_OBJECTS: tuple[ObjectData, ...] = tuple(obj for obj in GLOBAL_OBJECT_DATA if obj.unlockable)
UNLOCKABLE_OBJECTS_BY_NAME = {obj.name: obj for obj in UNLOCKABLE_OBJECTS}
UNLOCKABLE_OBJECT_VALUES = frozenset(obj.value for obj in UNLOCKABLE_OBJECTS)


def _parse_requirement(raw: Any) -> ObjectRequirement:
    if isinstance(raw, dict):
        name = raw["name"]
        return ObjectRequirement(
            name=name,
            selected_value=int(raw["value"]),
            global_value=UNLOCKABLE_OBJECTS_BY_NAME.get(name).value if name in UNLOCKABLE_OBJECTS_BY_NAME else None,
        )
    if isinstance(raw, int):
        obj = OBJECT_BY_VALUE[raw]
        return ObjectRequirement(obj.name, obj.value, obj.value)
    raise TypeError(f"Unsupported object requirement: {raw!r}")


def _parse_global_requirement(raw: Any) -> list[ObjectRequirement]:
    if isinstance(raw, str) and re.fullmatch(r"\d+-\d+", raw):
        return [_parse_requirement(value) for value in _expand_object_range(raw)]
    return [_parse_requirement(raw)]


def _build_challenge_table() -> dict[tuple[str, int], ChallengeData]:
    table: dict[tuple[str, int], ChallengeData] = {}
    raw_data = _load_json("challenge_object_values.json")
    for world_label, challenge_map in raw_data.items():
        key = _world_key(world_label)
        if key is None:
            continue
        for challenge_label, challenge_raw in challenge_map.items():
            challenge_index = int(challenge_label)
            challenge_type = challenge_raw["type"]
            world_name = "Hub World" if key == HUB_WORLD_KEY else WORLD_NAMES[key]
            raw_objects = challenge_raw.get("objects", [])
            if challenge_raw.get("special") == "Contraption-o-matic" and not raw_objects:
                raw_objects = ["37-41"]
            requirements: list[ObjectRequirement] = []
            if challenge_type == "local":
                requirements = [_parse_requirement(raw) for raw in raw_objects]
            else:
                for raw in raw_objects:
                    requirements.extend(_parse_global_requirement(raw))
            table[(key, challenge_index)] = ChallengeData(
                world_key=key,
                world_name=world_name,
                challenge=challenge_index,
                challenge_type=challenge_type,
                spark_reward=int(challenge_raw["spark_reward"] or 1),
                special=challenge_raw.get("special"),
                block_value=challenge_raw.get("block_value"),
                objects=tuple(requirements),
            )
    return table


CHALLENGE_TABLE = _build_challenge_table()
ALL_CHALLENGES: tuple[ChallengeData, ...] = tuple(
    CHALLENGE_TABLE[(world_key, challenge)]
    for world_key in WORLD_KEYS
    for challenge in range(1, 11)
)

HUB_CHALLENGE_DATA = CHALLENGE_TABLE[(HUB_WORLD_KEY, 1)]

SCORETACULAR_POSSIBLE_REQUIREMENTS = (
    PossibleChallengeRequirement(("Bouncer",)),
    PossibleChallengeRequirement(("Teleporter",), 1),
    PossibleChallengeRequirement(("Perfect Teleporter",), 1),
)

POSSIBLE_CHALLENGE_REQUIREMENTS: dict[tuple[str, int], tuple[PossibleChallengeRequirement, ...]] = {
    ("W02", 1): (PossibleChallengeRequirement(("Jumbo Ramp",)),),
    ("W02", 2): (PossibleChallengeRequirement(("Beach Buggy", "Jumbo Ramp")),),
    ("W02", 3): (PossibleChallengeRequirement(("Tow Truck",)),),
    ("W02", 4): (PossibleChallengeRequirement(("Jumbo Ramp",)),),
    ("W02", 5): (PossibleChallengeRequirement(("Jumbo Ramp",)),),
    ("W02", 6): (PossibleChallengeRequirement(("Jumbo Ramp",)),),
    ("W02", 7): (PossibleChallengeRequirement(("Temporary Glue", "Horseshoe Magnet")),),
    ("W02", 8): (PossibleChallengeRequirement(("Girder",)), PossibleChallengeRequirement(("Drivewheel",))),
    ("W02", 9): (PossibleChallengeRequirement(("Tow Rocket", "Horseshoe Magnet")),),
    ("W02", 10): (PossibleChallengeRequirement(("Bouncer",)),),
    ("W01", 1): (PossibleChallengeRequirement(("Jumbo Ramp",)),),
    ("W01", 2): (PossibleChallengeRequirement(("Basketball",)),),
    ("W01", 3): (PossibleChallengeRequirement(("Automatic Rocket",)),),
    ("W01", 4): (PossibleChallengeRequirement(("Automatic Fan",)),),
    ("W01", 5): (PossibleChallengeRequirement(("Automatic Fan", "Balloon")),),
    ("W01", 6): (PossibleChallengeRequirement(("Elephant Balloon", "Jumbo Ramp")),),
    ("W01", 7): (PossibleChallengeRequirement(("Jumbo Ramp",), 3),),
    ("W01", 8): (
        PossibleChallengeRequirement(("Long Block",)),
        PossibleChallengeRequirement(("Block",)),
        PossibleChallengeRequirement(("Girder",)),
    ),
    ("W01", 9): (PossibleChallengeRequirement(("Drivewheel",)),),
    ("W01", 10): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W03", 1): (PossibleChallengeRequirement(("Lawn Mower", "Jumbo Ramp")),),
    ("W03", 2): (PossibleChallengeRequirement(("Automatic Fan",)),),
    ("W03", 3): (PossibleChallengeRequirement(("Spring Pad Ramp",)),),
    ("W03", 4): (PossibleChallengeRequirement(("Long Block",)), PossibleChallengeRequirement(("Block",))),
    ("W03", 5): (PossibleChallengeRequirement(("Spring Pad Ramp",)),),
    ("W03", 6): (PossibleChallengeRequirement(("Spring Pad Ramp",)),),
    ("W03", 7): (PossibleChallengeRequirement(("Jumbo Ramp",)),),
    ("W03", 8): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W03", 9): (PossibleChallengeRequirement(("Blast Bomb", "Spring Pad Ramp"), 1),),
    ("W03", 10): (PossibleChallengeRequirement(("Spring Pad Ramp",)),),
    ("W04", 1): (PossibleChallengeRequirement(("Jumbo Ramp",)), PossibleChallengeRequirement(("Automatic Rocket",))),
    ("W04", 2): (PossibleChallengeRequirement(("Block",)), PossibleChallengeRequirement(("Long Block",))),
    ("W04", 3): (PossibleChallengeRequirement(("Bouncer", "Teleporter")),),
    ("W04", 4): (PossibleChallengeRequirement(("Laser Cannon", "Rock no. 42")),),
    ("W04", 5): (PossibleChallengeRequirement(("Spring Pad Ramp", "Ladder")),),
    ("W04", 6): (PossibleChallengeRequirement(("Block",)), PossibleChallengeRequirement(("Long Block",))),
    ("W04", 7): (PossibleChallengeRequirement(("Laser Cannon", "Rock no. 42")),),
    ("W04", 8): (PossibleChallengeRequirement(("Space Mine",)),),
    ("W04", 10): (
        PossibleChallengeRequirement(("Girder", "Drivewheel", "Long Block")),
        PossibleChallengeRequirement(("Girder", "Drivewheel", "Block")),
    ),
    ("W05", 1): (PossibleChallengeRequirement(("Balloon", "Outdoor Trailer", "Tractor")),),
    ("W05", 2): (PossibleChallengeRequirement(("Automatic Fan",)),),
    ("W05", 3): (PossibleChallengeRequirement(("Block",)), PossibleChallengeRequirement(("Long Block",))),
    ("W05", 5): (PossibleChallengeRequirement(("Jumbo Ramp",), 1),),
    ("W05", 6): (PossibleChallengeRequirement(("Block",)), PossibleChallengeRequirement(("Long Block",))),
    ("W05", 7): (PossibleChallengeRequirement(("Spring Pad Ramp", "Jumbo Ramp")),),
    ("W05", 8): (PossibleChallengeRequirement(("Horseshoe Magnet",)),),
    ("W05", 9): (PossibleChallengeRequirement(("Blast Bomb", "Horseshoe Magnet"), 1),),
    ("W05", 10): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W08", 1): (
        PossibleChallengeRequirement(("Automatic Fan", "Marker Cone")),
        PossibleChallengeRequirement(("Automatic Fan", "Packing Pallet")),
    ),
    ("W08", 3): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W08", 5): (PossibleChallengeRequirement(("Spring Pad Ramp", "Tall Steps")),),
    ("W08", 7): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W08", 8): (PossibleChallengeRequirement(("Teleporter",)),),
    ("W08", 9): (PossibleChallengeRequirement(("Balloon",)),),
    ("W06", 1): (PossibleChallengeRequirement(("Egyptian Obelisk",)),),
    ("W06", 2): (PossibleChallengeRequirement(("Blast Bomb", "Spring Pad Ramp")),),
    ("W06", 3): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W06", 5): (PossibleChallengeRequirement(("Blast Bomb", "Jumbo Ramp"), 3),),
    ("W06", 6): (PossibleChallengeRequirement(("Block",)), PossibleChallengeRequirement(("Long Block",))),
    ("W06", 9): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W07", 1): (PossibleChallengeRequirement(("Haz-chem Canister", "Jumbo Ramp", "Temporary Glue")),),
    ("W07", 2): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W07", 3): (
        PossibleChallengeRequirement(("Ramp-Bot", "Spring Pad 3000", "Horseshoe Magnet", "Spring Pad Ramp")),
    ),
    ("W07", 4): (PossibleChallengeRequirement(("Long Block",)), PossibleChallengeRequirement(("Block",), 3)),
    ("W07", 7): (PossibleChallengeRequirement(("Jumbo Ramp", "Magnet-Bot")),),
    ("W07", 9): (PossibleChallengeRequirement(("Haz-chem Canister", "Temporary Glue", "Lazy-Bot")),),
    ("W07", 10): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W09", 1): (PossibleChallengeRequirement(("Pop-Up Barrel", "Pirate Boot")),),
    ("W09", 2): (
        PossibleChallengeRequirement(("Girder", "Long Block", "Hinge")),
        PossibleChallengeRequirement(("Girder", "Block", "Hinge")),
    ),
    ("W09", 5): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W09", 6): (PossibleChallengeRequirement(("Bouncer", "Burster")),),
    ("W09", 10): (PossibleChallengeRequirement(("Long Block",)), PossibleChallengeRequirement(("Block",))),
    ("W10", 1): (PossibleChallengeRequirement(("Horseshoe Magnet", "Dart Rocket", "Bouncer")),),
    ("W10", 2): (PossibleChallengeRequirement(("Blast Bomb",)),),
    ("W10", 3): (
        PossibleChallengeRequirement(("Girder",)),
        PossibleChallengeRequirement(("Long Block",)),
        PossibleChallengeRequirement(("Block",)),
    ),
    ("W10", 4): (PossibleChallengeRequirement(("Blast Bomb", "Battering Ram (Low)", "Dart Rocket")),),
    ("W10", 8): (
        PossibleChallengeRequirement(("Balloon", "Small Ramp", "Knight Armour")),
        PossibleChallengeRequirement(("Balloon", "Small Ramp", "Heaven Armour")),
    ),
    ("W10", 9): (
        PossibleChallengeRequirement(("Girder", "Drivewheel", "Long Block")),
        PossibleChallengeRequirement(("Girder", "Drivewheel", "Block")),
    ),
    ("W11", 1): (PossibleChallengeRequirement(("Girder",)),),
    ("W11", 2): (PossibleChallengeRequirement(("Teleporter",)),),
    ("W11", 3): (PossibleChallengeRequirement(("Bouncer", "Teleporter")),),
    ("W11", 4): (
        PossibleChallengeRequirement(("Girder", "Drivewheel", "Long Block")),
        PossibleChallengeRequirement(("Girder", "Drivewheel", "Block")),
    ),
    ("W11", 7): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W11", 10): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W12", 2): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W12", 5): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W12", 8): (PossibleChallengeRequirement(("Soccer Ball", "Spring Pad Ramp")),),
    ("W12", 10): (
        PossibleChallengeRequirement(("Girder", "Drivewheel", "Long Block")),
        PossibleChallengeRequirement(("Girder", "Drivewheel", "Block")),
    ),
    ("W13", 1): (PossibleChallengeRequirement(("Dark Matter",)),),
    ("W13", 2): (PossibleChallengeRequirement(("Space Mine", "Spring Pad Ramp")),),
    ("W13", 3): (
        PossibleChallengeRequirement(("Girder", "Drivewheel", "Long Block")),
        PossibleChallengeRequirement(("Girder", "Drivewheel", "Block")),
    ),
    ("W13", 5): (PossibleChallengeRequirement(("Horseshoe Magnet", "Zero-Gravity Generator", "Space Mine")),),
    ("W13", 6): (
        PossibleChallengeRequirement(("Girder", "Drivewheel", "Long Block")),
        PossibleChallengeRequirement(("Girder", "Drivewheel", "Block")),
    ),
    ("W13", 9): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W13", 10): (PossibleChallengeRequirement(("Automatic Rocket", "Zero-Gravity Generator", "Teleporter")),),
    ("W14", 1): (PossibleChallengeRequirement(("Ultra Bounce Ball",)),),
    ("W14", 2): (PossibleChallengeRequirement(("Girder", "Drivewheel")),),
    ("W14", 5): (PossibleChallengeRequirement(("Spring Pad 3000",)),),
    ("W14", 6): (
        PossibleChallengeRequirement(("Girder", "Drivewheel", "Long Block")),
        PossibleChallengeRequirement(("Girder", "Drivewheel", "Block")),
    ),
    ("W14", 7): (PossibleChallengeRequirement(("Defense Laser", "Lazy-Bot")),),
    ("W14", 9): (
        PossibleChallengeRequirement(("Girder", "Long Block", "Hinge")),
        PossibleChallengeRequirement(("Girder", "Block", "Hinge")),
    ),
}

POSSIBLE_CHALLENGE_OBJECT_NAMES = frozenset(
    object_name
    for requirement_group in POSSIBLE_CHALLENGE_REQUIREMENTS.values()
    for requirement in requirement_group
    for object_name in requirement.objects
) | frozenset(
    object_name
    for requirement in SCORETACULAR_POSSIBLE_REQUIREMENTS
    for object_name in requirement.objects
)


def possible_challenge_requirements(
    challenge_data: ChallengeData,
    spark: int | None = None,
) -> tuple[PossibleChallengeRequirement, ...]:
    requirements = list(POSSIBLE_CHALLENGE_REQUIREMENTS.get((challenge_data.world_key, challenge_data.challenge), ()))
    if challenge_data.special == "Scoretacular":
        requirements.extend(SCORETACULAR_POSSIBLE_REQUIREMENTS)
    if spark is not None:
        requirements = [
            requirement
            for requirement in requirements
            if requirement.max_spark is None or spark <= requirement.max_spark
        ]
    return tuple(dict.fromkeys(requirements))


def challenge_logic_object_names(challenge_data: ChallengeData) -> tuple[str, ...]:
    if challenge_data.special == "Scoretacular":
        return ("Bouncer",)
    return tuple(
        requirement.name
        for requirement in challenge_data.objects
        if requirement.global_value in UNLOCKABLE_OBJECT_VALUES
    )


def challenge_logic_object_groups(
    challenge_data: ChallengeData,
    spark: int | None = None,
) -> tuple[tuple[str, ...], ...]:
    if challenge_data.special == "Scoretacular":
        if spark is not None and spark >= 4:
            return (("Bouncer", "Teleporter"), ("Bouncer", "Perfect Teleporter"))
        groups = [
            requirement.objects
            for requirement in POSSIBLE_CHALLENGE_REQUIREMENTS.get(
                (challenge_data.world_key, challenge_data.challenge), ()
            )
            if requirement.max_spark is not None
            and (spark is None or spark <= requirement.max_spark)
        ]
        # Some Scoretaculars have a tested challenge-specific route for their
        # first Spark, while the others need the standard single-object route.
        if not groups or spark is None or 2 <= spark <= 3:
            groups.extend((("Bouncer",), ("Teleporter",), ("Perfect Teleporter",)))
        return tuple(dict.fromkeys(groups))
    return (challenge_logic_object_names(challenge_data),)


def challenge_has_out_of_logic_possible(challenge_data: ChallengeData, spark: int | None = None) -> bool:
    strict_groups = {
        frozenset(group)
        for group in challenge_logic_object_groups(challenge_data, spark)
    }
    for possible_requirement in possible_challenge_requirements(challenge_data, spark):
        if frozenset(possible_requirement.objects) not in strict_groups:
            return True
    return False

RAM_MAP = _load_json("ram_map.json")
RAM_ADDRESSES = RAM_MAP["addresses"]
CHALLENGE_RECORDS = RAM_MAP["challenge_records"]["records"]
II_WORLD_FLAGS_BY_NAME = RAM_MAP["ii_world_flags"]

CONFIRMED_CURRENT_WORLD_IDS = {
    2: "W01",
    3: "W02",
    4: "W03",
    5: "W04",
}
EXPECTED_CURRENT_WORLD_IDS = {
    index + 2: world_key
    for index, world_key in enumerate(WORLD_KEYS)
}


def world_access_item_name(world_key: str) -> str:
    return f"{WORLD_NAMES[world_key]} Access"


def object_item_name(object_name: str) -> str:
    return object_name


def required_object_values(world_keys: tuple[str, ...] | None = None) -> frozenset[int]:
    world_key_filter = set(world_keys) if world_keys is not None else None
    required_values = {
        requirement.global_value
        for challenge in (HUB_CHALLENGE_DATA, *ALL_CHALLENGES)
        if challenge.world_key == HUB_WORLD_KEY or world_key_filter is None or challenge.world_key in world_key_filter
        for requirement in challenge.objects
        if requirement.global_value in UNLOCKABLE_OBJECT_VALUES
    }
    if any(
        challenge.special == "Scoretacular"
        and (world_key_filter is None or challenge.world_key in world_key_filter)
        for challenge in ALL_CHALLENGES
    ):
        required_values.add(UNLOCKABLE_OBJECTS_BY_NAME["Perfect Teleporter"].value)
    return frozenset(required_values)


@lru_cache(maxsize=None)
def _balanced_spark_count_candidates(total: int, item_limit: int) -> tuple[tuple[int, int, int, int], ...]:
    best_score: tuple[int, int, int, int] | None = None
    best_counts: list[tuple[int, int, int, int]] = []
    for count_6 in range(min(total // 6, item_limit) + 1):
        for count_3 in range(min((total - count_6 * 6) // 3, item_limit - count_6) + 1):
            remaining_after_3 = total - count_6 * 6 - count_3 * 3
            min_count_2 = max(0, count_6 + count_3 + remaining_after_3 - item_limit)
            max_count_2 = min(remaining_after_3 // 2, item_limit - count_6 - count_3)
            pivots = {
                min_count_2,
                max_count_2,
                remaining_after_3 // 3,
                count_6,
                count_3,
                (remaining_after_3 - count_6) // 2,
                (remaining_after_3 - count_3) // 2,
            }
            candidate_count_2s = {
                pivot + offset
                for pivot in pivots
                for offset in range(-2, 3)
                if min_count_2 <= pivot + offset <= max_count_2
            }
            for count_2 in candidate_count_2s:
                count_1 = remaining_after_3 - count_2 * 2
                counts = (count_1, count_2, count_3, count_6)
                if sum(counts) > item_limit:
                    continue
                presence = sum(count > 0 for count in counts)
                spread = max(counts) - min(counts)
                squared_imbalance = sum((count * 4 - sum(counts)) ** 2 for count in counts)
                score = (presence, -spread, -squared_imbalance, sum(counts))
                if best_score is None or score > best_score:
                    best_score = score
                    best_counts = [counts]
                elif score == best_score:
                    best_counts.append(counts)
    return tuple(best_counts)


def spark_item_amounts_for_total(
    total: int,
    random_source: Any | None = None,
    max_count: int | None = None,
) -> list[int]:
    if total < 0 or total > 610:
        raise ValueError(f"Create required spark total must be between 0 and 610, got {total}.")
    if total == 0:
        return []

    item_limit = total if max_count is None else max_count
    best_counts = _balanced_spark_count_candidates(total, item_limit)
    if not best_counts:
        raise ValueError(f"Could not build Create AP Spark amount list for total {total} in {item_limit} items.")
    counts = random_source.choice(best_counts) if random_source is not None else best_counts[0]
    result = [amount for amount, count in zip((1, 2, 3, 6), counts) for _ in range(count)]
    if random_source is not None:
        random_source.shuffle(result)
    return result


def spark_item_name(amount: int) -> str:
    return SPARK_ITEM_BY_AMOUNT[amount]


def challenge_location_name(world_key: str, challenge: int) -> str:
    if world_key == HUB_WORLD_KEY:
        return "Hub World Challenge 1"
    return f"{WORLD_NAMES[world_key]} Challenge {challenge:02d}"


def spark_location_name(world_key: str, challenge: int, spark: int) -> str:
    if world_key == HUB_WORLD_KEY:
        return "Hub World Challenge 1 - Reward"
    return f"{challenge_location_name(world_key, challenge)} Spark {spark}"


def create_chain_location_name(world_key: str, chain: int) -> str:
    return f"{WORLD_NAMES[world_key]} Create Chain {chain}"


def hub_create_chain_location_name() -> str:
    return "Hub World Create Chain"


def region_name(world_key: str) -> str:
    if world_key == HUB_WORLD_KEY:
        return "Hub World"
    return WORLD_NAMES[world_key]


def world_key_from_name(world_name: str) -> str:
    return WORLD_KEY_BY_NAME[world_name]
