"""Bounded extraction of the observed LegoCityPickups save section; no writes."""
import struct

SECTION_HASH = 0x9437DD86
PAYLOAD_SIZE = 1600


def extract_section(data: bytes) -> tuple[int, bytes]:
    header = struct.pack("<II", SECTION_HASH, PAYLOAD_SIZE)
    closing = struct.pack("<I", SECTION_HASH)
    matches = []
    start = 0
    while (hit := data.find(header, start)) >= 0:
        start = hit + 1
        payload_offset = hit + len(header)
        end = payload_offset + PAYLOAD_SIZE
        if data[end:end + 4] == closing:
            matches.append((payload_offset, data[payload_offset:end]))
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous bounded LegoCityPickups section")
    return matches[0]


def set_bits(payload: bytes) -> list[int]:
    """Return raw bit offsets, not yet mapped to individual collectible identities."""
    if len(payload) != PAYLOAD_SIZE:
        raise ValueError("Invalid pickup payload size")
    return [offset * 8 + bit for offset, value in enumerate(payload)
            for bit in range(8) if value & (1 << bit)]
