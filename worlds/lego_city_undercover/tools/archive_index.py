"""Read-only CC4 v2 archive index and bounded extraction of raw/DFLT entries.

Format reference: linterniGamer/Tt-Games-quickbms-scripts, files/ttgames_LCU.bms.
Only CRC-verified names are accepted; unsupported compression fails closed.
"""
from __future__ import annotations

import argparse
import collections
import json
import struct
import zlib
from pathlib import Path, PureWindowsPath


def name_crc(name: str) -> int:
    value = 0x811C9DC5
    for byte in name.upper().replace("/", "\\").encode("ascii"):
        value = ((value ^ byte) * 0x199933) & 0xFFFFFFFF
    return value


def rc4(data: bytes, key: bytes) -> bytes:
    """Decode the archive's ZIPX obfuscation; not a security primitive."""
    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + key[i % len(key)]) & 255
        state[i], state[j] = state[j], state[i]
    i = j = 0
    output = bytearray()
    for byte in data:
        i = (i + 1) & 255
        j = (j + state[i]) & 255
        state[i], state[j] = state[j], state[i]
        output.append(byte ^ state[(state[i] + state[j]) & 255])
    return bytes(output)


def parse_index(data: bytes, archive_size: int) -> list[dict]:
    if len(data) < 32 or data[4:12] != b".CC40TAD":
        raise ValueError("Unsupported index magic")
    kind, version, files, names, string_size = struct.unpack_from(">iIIII", data, 12)
    if kind != -11 or version != 2:
        raise ValueError(f"Unsupported index variant: {kind}, {version}")
    names_end = 32 + string_size
    entries_start = names_end + 4 + names * 12
    crc_start = entries_start + 8 + files * 16
    if crc_start + files * 4 > len(data):
        raise ValueError("Truncated index")
    if struct.unpack_from(">iI", data, entries_start) != (kind, files):
        raise ValueError("Inconsistent file table")
    folders: dict[int, str] = {0: ""}
    paths = []
    for index in range(names):
        off, parent, unused, some, file_id = struct.unpack_from(">IHHhH", data, names_end + 4 + index * 12)
        if off == 0xFFFFFFFF:
            continue
        if off >= string_size or parent not in folders:
            raise ValueError("Invalid name offset/parent")
        start = 32 + off
        end = data.find(b"\0", start, names_end)
        if end < 0:
            raise ValueError("Unterminated name")
        name = data[start:end].decode("ascii")
        path = (folders[parent] + "\\" + name).lstrip("\\")
        if file_id or index == names - 1:
            paths.append(path)
        else:
            folders[index] = path
    lookup: dict[int, str] = {}
    for path in paths:
        crc = name_crc(path)
        if crc in lookup:
            raise ValueError("Duplicate/colliding name CRC")
        lookup[crc] = path
    result = []
    for index in range(files):
        offset, packed_size, size_flags = struct.unpack_from(">QII", data, entries_start + 8 + index * 16)
        crc = struct.unpack_from(">I", data, crc_start + index * 4)[0]
        size = size_flags & 0x7FFFFFFF
        if offset + packed_size > archive_size:
            raise ValueError("Entry exceeds archive bounds")
        result.append(dict(index=index, path=lookup.get(crc), crc=f"{crc:08x}", offset=offset,
                           packed_size=packed_size, size=size, packed=bool(size_flags >> 31)))
    return result


def read_index(archive: Path) -> list[dict]:
    with archive.open("rb") as stream:
        first, size = struct.unpack("<II", stream.read(8))
        offset = ((first ^ 0xFFFFFFFF) << 8) + 256 if first & 0x80000000 else first
        if size > 64 * 1024 * 1024 or offset + size > archive.stat().st_size:
            raise ValueError("Invalid index bounds")
        stream.seek(offset)
        return parse_index(stream.read(size), archive.stat().st_size)


def extract(archive: Path, entry: dict, limit: int = 16 * 1024 * 1024) -> bytes:
    if max(entry["size"], entry["packed_size"]) > limit:
        raise ValueError("Entry exceeds extraction limit")
    with archive.open("rb") as stream:
        stream.seek(entry["offset"])
        data = stream.read(entry["packed_size"])
    if not entry["packed"] and len(data) == entry["size"]:
        return data
    output = bytearray()
    position = 0
    while position < len(data):
        signature = data[position:position + 4]
        if signature not in (b"DFLT", b"ZIPX") or position + 12 > len(data):
            raise ValueError("Unsupported compression signature")
        packed, size = struct.unpack_from("<II", data, position + 4)
        position += 12
        if position + packed > len(data) or len(output) + size > limit:
            raise ValueError("Invalid compression chunk")
        chunk = data[position:position + packed]
        if signature == b"ZIPX":
            chunk = rc4(chunk, struct.pack("<I", packed))
        if packed != size:
            decoder = zlib.decompressobj(-15)
            chunk = decoder.decompress(chunk, size + 1)
            if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                raise ValueError("Invalid deflate stream")
        if len(chunk) != size:
            raise ValueError("Chunk size mismatch")
        output.extend(chunk)
        position += packed
    if len(output) != entry["size"]:
        raise ValueError("Extracted size mismatch")
    return bytes(output)


def safe_target(root: Path, name: str) -> Path:
    path = PureWindowsPath(name)
    if path.is_absolute() or path.drive or any(part in ("..", ".") or ":" in part for part in path.parts):
        raise ValueError("Unsafe archive path")
    target = root.joinpath(*path.parts).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError("Archive path escapes output directory")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", help="Case-insensitive substring of CRC-validated paths")
    args = parser.parse_args()
    world = Path(__file__).resolve().parents[1]
    output = world / "notes/analysis"
    output.mkdir(parents=True, exist_ok=True)
    summary = []
    for archive in sorted((world / "notes/gamefiles").glob("*.DAT")):
        entries = read_index(archive)
        (output / (archive.name + ".json")).write_text(json.dumps(entries, indent=2), encoding="utf-8")
        row = dict(archive=archive.name, entries=len(entries), verified_names=sum(e["path"] is not None for e in entries),
                   extensions=dict(collections.Counter(PureWindowsPath(e["path"]).suffix.lower()
                                                       for e in entries if e["path"])))
        summary.append(row)
        print(json.dumps(row), flush=True)
        if args.extract:
            for entry in entries:
                if entry["path"] and args.extract.lower() in entry["path"].lower():
                    target = safe_target(world / "notes/extracted" / archive.stem, entry["path"])
                    try:
                        data = extract(archive, entry)
                    except ValueError as error:
                        print(entry["path"], str(error), flush=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open("xb") as stream:
                        stream.write(data)
    (output / "archive_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
