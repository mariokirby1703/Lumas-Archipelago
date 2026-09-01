from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from .world_constants import CREATE_CHAINS_PER_WORLD, HUB_WORLD_KEY, SPARK_ITEM_BY_AMOUNT
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
    ("W06", 1): (PossibleChallengeRequirement(("Egyptian Obelisk", "Canopic Jar")),),
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


def challenge_has_out_of_logic_possible(challenge_data: ChallengeData, spark: int | None = None) -> bool:
    strict_objects = frozenset(challenge_logic_object_names(challenge_data))
    for possible_requirement in possible_challenge_requirements(challenge_data, spark):
        if possible_requirement.max_spark is not None:
            return True
        if frozenset(possible_requirement.objects) != strict_objects:
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
    return frozenset(
        requirement.global_value
        for challenge in (HUB_CHALLENGE_DATA, *ALL_CHALLENGES)
        if challenge.world_key == HUB_WORLD_KEY or world_key_filter is None or challenge.world_key in world_key_filter
        for requirement in challenge.objects
        if requirement.global_value in UNLOCKABLE_OBJECT_VALUES
    )


def _vanilla_spark_amounts() -> list[int]:
    amounts = [
        challenge.spark_reward
        for challenge in (HUB_CHALLENGE_DATA, *ALL_CHALLENGES)
    ]
    amounts.extend([1] * (len(WORLD_KEYS) * CREATE_CHAINS_PER_WORLD + 1))
    return amounts


def spark_item_amounts_for_total(
    total: int,
    random_source: Any | None = None,
    max_count: int | None = None,
) -> list[int]:
    if total < 0 or total > 610:
        raise ValueError(f"Create required spark total must be between 0 and 610, got {total}.")
    available_amounts = _vanilla_spark_amounts()
    if sum(available_amounts) != 610:
        raise ValueError("Create vanilla AP Spark amount table must sum to 610.")
    if total == 610:
        result = list(available_amounts)
        if max_count is not None and len(result) > max_count:
            result = _compact_spark_amounts(total, max_count, random_source)
        if random_source is not None:
            random_source.shuffle(result)
        return result

    amount_to_remove = 610 - total
    removal_candidates = _spark_removal_candidates(available_amounts, total)
    if random_source is not None:
        random_source.shuffle(removal_candidates)

    min_remove_count = max(0, len(available_amounts) - max_count) if max_count is not None else 0
    reachable: dict[int, list[int]] = {0: []}
    for amount in removal_candidates:
        for subtotal, amounts in tuple(reachable.items()):
            next_total = subtotal + amount
            if next_total > amount_to_remove:
                continue
            next_amounts = [*amounts, amount]
            if len(next_amounts) > len(reachable.get(next_total, [])):
                reachable[next_total] = next_amounts

    if amount_to_remove in reachable and len(reachable[amount_to_remove]) >= min_remove_count:
        removed = Counter(reachable[amount_to_remove])
        result = []
        for amount in available_amounts:
            if removed[amount]:
                removed[amount] -= 1
            else:
                result.append(amount)
    elif max_count is not None:
        result = _compact_spark_amounts(total, max_count, random_source)
    else:
        raise ValueError(f"Could not build Create AP Spark amount list for total {total}.")

    if random_source is not None:
        random_source.shuffle(result)
    return result


def _spark_removal_candidates(available_amounts: list[int], total: int) -> list[int]:
    if total < sum(amount for amount in set(available_amounts)):
        return list(available_amounts)

    counts = Counter(available_amounts)
    candidates: list[int] = []
    for amount in sorted(counts):
        minimum_remaining = min(5, counts[amount])
        candidates.extend([amount] * max(0, counts[amount] - minimum_remaining))
    return candidates


def _compact_spark_amounts(total: int, max_count: int, random_source: Any | None = None) -> list[int]:
    if total == 0:
        return []
    if max_count <= 0:
        raise ValueError(f"Create AP Spark total {total} cannot fit into {max_count} items.")

    available_counts = Counter(_vanilla_spark_amounts())
    reachable: dict[tuple[int, int], Counter[int]] = {(0, 0): Counter()}
    for amount in (6, 3, 2, 1):
        for _ in range(available_counts[amount]):
            for (subtotal, count), amounts in tuple(reachable.items()):
                next_total = subtotal + amount
                next_count = count + 1
                if next_total > total or next_count > max_count or (next_total, next_count) in reachable:
                    continue
                next_amounts = amounts.copy()
                next_amounts[amount] += 1
                reachable[(next_total, next_count)] = next_amounts

    possible_counts = [
        count
        for candidate_total, count in reachable
        if candidate_total == total
    ]
    if not possible_counts:
        raise ValueError(f"Could not build Create AP Spark amount list for total {total}.")

    minimum_count = min(possible_counts)
    preferred_counts = [
        count
        for count in possible_counts
        if count <= min(max_count, minimum_count + 20)
    ]
    count = max(preferred_counts)
    amounts = reachable[(total, count)]

    result: list[int] = []
    for amount in (1, 2, 3, 6):
        result.extend([amount] * amounts[amount])

    if total >= 12:
        missing_amounts = [amount for amount in (1, 2, 3, 6) if amounts[amount] == 0]
        for missing_amount in missing_amounts:
            for index, amount in enumerate(result):
                replacement_total = total - amount + missing_amount
                if replacement_total == total:
                    continue
                try:
                    replacement_tail = _compact_spark_amounts(
                        total - missing_amount,
                        max_count - 1,
                        random_source,
                    )
                except ValueError:
                    continue
                result = [missing_amount, *replacement_tail]
                break

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
