"""Read selected named Job values through the game's statically identified registry.

Resource names, runtime hashes and concrete value types must all agree. No writes.
"""
from __future__ import annotations

import struct

from inventory_reader import Read, pointer
from research_profile import symbol_hash

JOB_MANAGER_RVA = 0x17ECA08
VALUE_VTABLES = {0xC46B38: "Int", 0xC46BB8: "Bool"}
QUERIES = {
    "Flow_Setup": {"Flow_Act": "Int", "Flow_Start": "Int", "DialogueStoryStage": "Int"},
    "Flow_Setup.Act_1": {"Act1_Mission": "Int", "Act1_Stage": "Int"},
    "Flow_Setup.Act_2": {"Act2_Mission": "Int", "Act2_Stage": "Int"},
    "Flow_Setup.Act_3": {"Act3_Mission": "Int", "Act3_Stage": "Int"},
    "Flow_Setup.Act_4": {"Act4_Mission": "Int", "Act4_Stage": "Int"},
    "Flow_Setup.Act_1.LCPD": {"LCPD_Stage": "Int", "IntroPlayed": "Bool"},
    "Flow_Setup.Act_1.LCPD.LCPD_Level.LCPD_Lobby": {"LCPD_LobbyEntered": "Int", "LCPD_MainframeActive": "Bool"},
    "Flow_Setup.Flow_Completed": {"Act_1_GoToPoliceStation": "Bool", "Act_1_CatchRobber_1": "Bool",
                                  "Act_1_CatchRobber_2": "Bool", "Act_1_CatchRobber_3": "Bool",
                                  "Act_1_RoadBlockRemoved": "Bool", "Act_1_GetGrappleGun": "Bool",
                                  "Act_1_EnterPrison": "Bool"},
    "Standalones.Prison": {"Finished": "Int", "WardensOffice": "Int", "Painting_Opened": "Int",
                            "Rex_Enemies": "Int", "Rex_Conversation": "Int", "Switch01": "Int",
                            "Switch02": "Int", "Switch03": "Int", "Rex_Punchbag": "Int"},
    "Flow_Saves.Act_1.Meet_Blue_at_Prison": {"MeetBluePrison": "Bool"},
    "Flow_Saves.Act_1.Fix_Road_Block": {"RoadBlockFlowObjects": "Bool"},
    "Standalones.MoonBase": {"Finished": "Int", "CutsceneStage": "Int"},
}


def parse_job_registry(data: bytes) -> dict[int, tuple[int, int]]:
    if len(data) % 24 or len(data) > 4096 * 24:
        raise ValueError("Invalid job registry span")
    result = {}
    for offset in range(0, len(data), 24):
        name_hash, field_pointer, field_count = struct.unpack_from("<I4xQH", data, offset)
        if name_hash in result or field_count > 128 or (field_count and not field_pointer):
            raise ValueError("Invalid or duplicate job record")
        result[name_hash] = (field_pointer, field_count)
    return result


def decode_job_value(data: bytes, base: int, expected_hash: int, expected_kind: str) -> int | bool:
    if len(data) != 20:
        raise ValueError("Incomplete JobValue")
    vtable = struct.unpack_from("<Q", data)[0] - base
    if struct.unpack_from("<I", data, 12)[0] != expected_hash:
        raise ValueError("JobValue hash changed")
    if VALUE_VTABLES.get(vtable) != expected_kind:
        raise ValueError("JobValue runtime type does not match the resource")
    if expected_kind == "Bool":
        if data[16] not in (0, 1):
            raise ValueError("Invalid Boolean JobValue")
        return bool(data[16])
    return struct.unpack_from("<i", data, 16)[0]


def read_story(read: Read, base: int) -> dict:
    manager = pointer(read, base + JOB_MANAGER_RVA)
    if not manager:
        return dict(status="not_initialized")
    descriptor = read(manager + 0xE0, 16)
    table, count = struct.unpack_from("<QI", descriptor)
    if count > 4096:
        raise ValueError("Job registry exceeds read limit")
    raw = b"".join(read(table + offset, min(4096, count * 24 - offset))
                   for offset in range(0, count * 24, 4096))
    registry = parse_job_registry(raw)
    jobs = {}
    for name, fields in QUERIES.items():
        record = registry.get(symbol_hash(name))
        if record is None:
            continue
        array, field_count = record
        objects = read(array, field_count * 8) if field_count else b""
        hashes = {symbol_hash(field): (field, kind) for field, kind in fields.items()}
        values = {}
        for offset in range(0, len(objects), 8):
            obj = struct.unpack_from("<Q", objects, offset)[0]
            data = read(obj, 20)
            field_hash = struct.unpack_from("<I", data, 12)[0]
            if field_hash in hashes:
                field, kind = hashes[field_hash]
                if field in values:
                    raise ValueError("Ambiguous JobValue field")
                values[field] = decode_job_value(data, base, field_hash, kind)
        if field_count and read(array, field_count * 8) != objects:
            raise RuntimeError("Job field list changed during snapshot; retry")
        jobs[name] = values
    if pointer(read, base + JOB_MANAGER_RVA) != manager or read(manager + 0xE0, 16) != descriptor:
        raise RuntimeError("Job registry changed during snapshot; retry")
    return dict(status="read", registry_job_count=count, jobs=jobs,
                scene_and_key_semantics="job values; not a verified held-object or scene-id query")
