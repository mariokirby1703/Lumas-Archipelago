"""Bounded read-only stats and character-state reader for the exact supported hash.

Pointer/field evidence is documented in docs/research/inventory_layout.md.
Found, owned, pending grants and co-op alternatives are kept separate.
"""
from __future__ import annotations

from collections.abc import Callable
import json
import pkgutil
import struct

Read = Callable[[int, int], bytes]
STATS_RVA = 0x1C7A830
PROFILE_RVA = 0x1C7F160
MODELS_RVA = 0x17EBD38
CONTROLLER_RVA = 0x17EBE20
CHARACTER_STATE_RVA = 0x1C7CBB8
MISSION_TOKENS_RVA = 0x11754B0


def read_model_ids(read,base):
    models=pointer(read,base+MODELS_RVA)
    count=struct.unpack('<I',read(models+0xE0,4))[0]
    table=pointer(read,models+0x118)
    if not 0<count<=1024:raise ValueError('Unsupported model count')
    result={};ambiguous=set();primary_exact={}
    primary={'COP','ROBBER','MINER','ASTRONAUT','FARMER','FIREMAN','CONSTRUCTION_LEGOCITYCONSTRUCTIONWORKER'}
    for index in range(count):
        record=pointer(read,table+index*8)
        if not record:continue
        name_pointer=pointer(read,record+0x30)
        if not name_pointer:continue
        raw_name=cstring(read,name_pointer);name=raw_name.upper()
        if raw_name in primary:primary_exact.setdefault(raw_name,[]).append(index)
        if not name or name in ambiguous:continue
        if name in result:
            ambiguous.add(name);del result[name];continue
        result[name]=index
    # COP and the unrelated resource name Cop collide only after uppercasing.
    # Keep the exact canonical name even after a player changes the class skin.
    result.update({name:ids[0] for name,ids in primary_exact.items() if len(ids)==1})
    # Native names can collide (COP/Cop). Primary class defaults are explicit
    # model IDs and disambiguate those seven progression disguises.
    controller=pointer(read,base+CONTROLLER_RVA)
    defaults=struct.unpack('<8h',read(controller+0x148,16))
    for index in defaults:
        if not 0<=index<count:continue
        record=pointer(read,table+index*8)
        if not record:continue
        name=cstring(read,pointer(read,record+0x30)).upper()
        result[name]=primary_exact[name][0] if name in primary_exact and len(primary_exact[name])==1 else index
    if pointer(read,base+MODELS_RVA)!=models or pointer(read,models+0x118)!=table:
        raise RuntimeError('Model table changed')
    return result


def parse_mission_token_ids(data: bytes) -> list[int]:
    """0x6a6f0 appends int16 model IDs at +0x52; +0x5a is the count."""
    if len(data)!=9 or data[8]>4:raise ValueError('Invalid mission token queue')
    ids=list(struct.unpack('<4h',data[:8]))[:data[8]]
    if any(not 0<=i<1024 for i in ids):raise ValueError('Invalid mission token model')
    return ids


def read_mission_tokens(read: Read, base: int) -> dict:
    manager=pointer(read,base+MISSION_TOKENS_RVA)
    if not manager:return dict(status='not_initialized',records=[])
    raw=read(manager+0x52,9);ids=parse_mission_token_ids(raw)
    models=pointer(read,base+MODELS_RVA)
    count=struct.unpack('<I',read(models+0xE0,4))[0]
    if not 0<count<=1024 or any(i>=count for i in ids):raise ValueError('Mission model outside table')
    table=pointer(read,models+0x118);rows=[]
    for model in ids:
        record=pointer(read,table+model*8)
        name=cstring(read,pointer(read,record+0x30))
        rows.append(dict(model_id=model,internal_name=name,evidence='native mission pickup queue'))
    if pointer(read,base+MISSION_TOKENS_RVA)!=manager or read(manager+0x52,9)!=raw:
        raise RuntimeError('Mission tokens changed during snapshot')
    return dict(status='read',records=rows,evidence='0x6a6f0; one live model 386 validation')


def pointer(read: Read, address: int) -> int:
    data = read(address, 8)
    if len(data) != 8:
        raise ValueError("Incomplete pointer read")
    return struct.unpack("<Q", data)[0]


def parse_stats(data: bytes, profile_studs: bytes) -> dict:
    if len(data) != 0x3A0 or len(profile_studs) != 8:
        raise ValueError("Incomplete inventory statistics")
    # Reproduce the branch in GetPlayerBricks' callee at RVA 0x3bf70.
    use_bank = bool(data[0x5D] or data[0x5E] or data[0x40])
    bricks_offset = 0x14 if use_bank else 0x18
    return dict(studs=struct.unpack("<Q", profile_studs)[0],
                super_bricks=struct.unpack_from("<I", data, bricks_offset)[0],
                gold_bricks=struct.unpack_from("<I", data, 0x364)[0],
                gold_brick_total=struct.unpack_from("<I", data, 0x360)[0],
                stats_stud_checkpoint=struct.unpack_from("<Q", data, 0x48)[0],
                super_brick_source_offset=hex(0x3300 + bricks_offset))


def read_stats(read: Read, base: int) -> dict:
    manager = pointer(read, base + STATS_RVA)
    profile = pointer(read, base + PROFILE_RVA)
    if not manager or not profile:
        return dict(status="not_initialized")
    result = parse_stats(read(manager + 0x3300, 0x3A0), read(profile + 0xFB10, 8))
    if pointer(read, base + STATS_RVA) != manager or pointer(read, base + PROFILE_RVA) != profile:
        raise RuntimeError("Stats object changed during snapshot; retry")
    return dict(status="read", **result)


def parse_character_control(data: bytes, extra_ids: list[int]) -> dict:
    if len(data) != 0x70 or any(type(index) is not int or not 0 <= index < 1024 for index in extra_ids):
        raise ValueError("Invalid character control snapshot")
    defaults = list(struct.unpack_from("<16h", data, 8))
    pending = list(struct.unpack_from("<16h", data, 0x2A))
    if any(index < -1 or index >= 1024 for index in defaults + pending):
        raise ValueError("Invalid default/pending model id")
    return dict(default_model_ids=defaults, pending_class_model_ids=pending, pending_extra_model_ids=extra_ids)


def cstring(read: Read, address: int) -> str:
    data = bytearray()
    for _ in range(8):
        size = min(32, 4096 - (address & 4095))
        chunk = read(address, size)
        if len(chunk) != size:
            raise ValueError("Incomplete model name read")
        end = chunk.find(b"\0")
        if end >= 0:
            return (data + chunk[:end]).decode("ascii")
        data.extend(chunk)
        address += size
    raise ValueError("Unterminated model name")


def read_characters(read: Read, base: int) -> dict:
    roster = json.loads(pkgutil.get_data(__name__, "collection_manifest.json"))
    models = pointer(read, base + MODELS_RVA)
    controller = pointer(read, base + CONTROLLER_RVA)
    state = pointer(read, base + CHARACTER_STATE_RVA)
    if not models or not controller or not state:
        return dict(status="not_initialized")
    header = read(models, 0x120)
    count = struct.unpack_from("<I", header, 0xE0)[0]
    table = struct.unpack_from("<Q", header, 0x118)[0]
    if not 0 < count <= 1024:
        raise ValueError("Unsupported model-table size")
    control_data = read(controller + 0x140, 0x70)
    extra_ptr = struct.unpack_from("<Q", control_data, 0x60)[0]
    extra_count = struct.unpack_from("<I", control_data, 0x6C)[0]
    if extra_count > 128:
        raise ValueError("Unexpected pending-character queue length")
    extra_data = read(extra_ptr, extra_count * 2) if extra_count else b""
    control = parse_character_control(control_data, list(struct.unpack(f"<{extra_count}h", extra_data)))
    pending = set(index for index in control["pending_class_model_ids"] if index >= 0)
    pending.update(control["pending_extra_model_ids"])
    if any(index >= count for index in pending):
        raise ValueError("Pending character exceeds model-table bounds")
    state_bytes = read(state, 0x80 + count)
    coop_defaults = {d["model"] for d in roster["defaults"] if d["player"] == 2}
    linked_civilian = {d["model"] for d in roster["defaults"] if d["linked"] and d["class_name"] == "generic"}
    rows = []
    for index in range(count):
        found = bool(state_bytes[index // 8] & (1 << (index % 8)))
        owned = state_bytes[0x80 + index]
        if not (found or owned or index in pending):
            continue
        record = pointer(read, table + index * 8)
        metadata = read(record, 0x38)
        name = cstring(read, struct.unpack_from("<Q", metadata, 0x30)[0])
        definition = roster["entries"].get(name.upper())
        if not definition:
            group = "unmapped_model"
        elif definition["kind"] == "vehicle":
            group = "vehicle"
        elif not definition["counts_for_progress"]:
            group = "non_progress_character"
        elif name.upper() in coop_defaults or name.upper() in linked_civilian:
            group = "coop_alternative"
        else:
            group = "character"
        rows.append(dict(model_id=index, internal_name=name, group=group,
                         found_bit=found, owned_byte=owned, pending_grant=index in pending,
                         unlock_candidate=bool(owned or index in pending)))
    if (pointer(read, base + MODELS_RVA) != models or pointer(read, base + CONTROLLER_RVA) != controller
            or pointer(read, base + CHARACTER_STATE_RVA) != state
            or read(models + 0xE0, 4) != header[0xE0:0xE4]
            or read(models + 0x118, 8) != header[0x118:0x120]
            or read(controller + 0x140, 0x70) != control_data
            or (extra_count and read(extra_ptr, extra_count * 2) != extra_data)
            or read(state, 0x80 + count) != state_bytes):
        raise RuntimeError("Character state changed during snapshot; retry")
    return dict(status="read", model_count=count, state_semantics="static evidence; partial live validation",
                characters=[row for row in rows if row["group"] == "character"],
                auxiliary_states=[row for row in rows if row["group"] != "character"],
                control=control)
