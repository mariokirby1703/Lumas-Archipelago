from __future__ import annotations

import json
import re
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


def spark_item_amounts_for_total(total: int) -> list[int]:
    if total < 0 or total > 610:
        raise ValueError(f"Create required spark total must be between 0 and 610, got {total}.")
    available_amounts = [
        challenge.spark_reward
        for challenge in (HUB_CHALLENGE_DATA, *ALL_CHALLENGES)
    ]
    available_amounts.extend([1] * (len(WORLD_KEYS) * CREATE_CHAINS_PER_WORLD + 1))
    available_amounts.sort(reverse=True)

    reachable: dict[int, list[int]] = {0: []}
    for amount in available_amounts:
        for subtotal, amounts in tuple(reachable.items()):
            next_total = subtotal + amount
            if next_total > total or next_total in reachable:
                continue
            reachable[next_total] = [*amounts, amount]
            if next_total == total:
                return reachable[next_total]
    return reachable[total]


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
