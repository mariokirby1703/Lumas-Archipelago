"""Experimental read-only objective table parser derived from IsComplete disassembly.

No live completion transition has validated this layout. Not an AP check source yet.
"""
from __future__ import annotations

import struct
from collections.abc import Callable

MAX_OBJECTIVES = 8192
MANAGER_POINTER_RVA = 0x17ECA28


def parse_record_groups(data: bytes) -> dict[int, list[int]]:
    if len(data) % 12 or len(data) > MAX_OBJECTIVES * 12:
        raise ValueError("Invalid objective record buffer size")
    result = {}
    for offset in range(0, len(data), 12):
        name_hash, bit_index = struct.unpack_from("<Ih", data, offset)
        if bit_index < 0:
            raise ValueError("Invalid objective record")
        result.setdefault(name_hash, []).append(bit_index)
    return result


def parse_records(data: bytes) -> dict[int, int]:
    groups = parse_record_groups(data)
    if any(len(indices) != 1 for indices in groups.values()):
        raise ValueError("Ambiguous objective hash")
    return {key: indices[0] for key, indices in groups.items()}


def decode_bits(records: dict[int, int], data: bytes) -> dict[int, bool]:
    if any(type(bit) is not int or not 0 <= bit <= 32767 for bit in records.values()):
        raise ValueError("Invalid completion bit index")
    if records and max(records.values()) // 8 >= len(data):
        raise ValueError("Completion bitset is too short")
    return {name_hash: bool(data[bit // 8] & (1 << (bit % 8))) for name_hash, bit in records.items()}


def read_objectives(read: Callable[[int, int], bytes], module_base: int) -> dict:
    original_read = read

    def read(address: int, size: int) -> bytes:
        data = original_read(address, size)
        if len(data) != size:
            raise ValueError("Incomplete objective memory read")
        return data

    def pointer(address):
        return struct.unpack("<Q", read(address, 8))[0]

    manager = pointer(module_base + MANAGER_POINTER_RVA)
    if not manager:
        return dict(status="not_initialized", evidence="static layout only")
    descriptor = read(manager + 0x950, 12)
    table = struct.unpack_from("<Q", descriptor)[0]
    count = struct.unpack_from("<h", descriptor, 10)[0]
    if not 0 <= count <= MAX_OBJECTIVES:
        raise ValueError("Unexpected objective table count")
    if not count:
        return dict(status="empty_table", evidence="static layout only")
    data = bytearray()
    while len(data) < count * 12:
        size = min(4096, count * 12 - len(data))
        data.extend(read(table + len(data), size))
    groups = parse_record_groups(bytes(data))
    records = {key: indices[0] for key, indices in groups.items() if len(indices) == 1}
    ambiguous = {str(key): indices for key, indices in groups.items() if len(indices) > 1}
    owner = pointer(manager + 0x978)
    bits_pointer = pointer(owner)
    size = (max(index for indices in groups.values() for index in indices) // 32 + 1) * 4
    bits = read(bits_pointer, size)
    if (pointer(module_base + MANAGER_POINTER_RVA) != manager
            or read(manager + 0x950, 12) != descriptor
            or pointer(manager + 0x978) != owner or pointer(owner) != bits_pointer):
        raise RuntimeError("Objective structures changed during snapshot; retry")
    values = decode_bits(records, bits)
    return dict(status="experimental_snapshot", evidence="static layout; completion transition unverified",
                manager_pointer=hex(manager), record_count=count,
                ambiguous_hashes=ambiguous,
                records=[dict(name_hash=key, bit_index=records[key], candidate_complete=value)
                         for key, value in values.items()])
