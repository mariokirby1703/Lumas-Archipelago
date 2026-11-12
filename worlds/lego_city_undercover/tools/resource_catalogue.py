"""Bounded v17 GIZ section inventory and literal scanner-name occurrence evidence.

Section payloads and the final name table remain opaque; no position or pickup layout is guessed.
"""
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path
import re
import struct


def sections(data: bytes) -> tuple[list[dict], int]:
    if data[:8] != struct.pack("<II", 17, 0):
        raise ValueError("Unsupported GIZ header")
    offset = 8
    result = []
    while offset + 4 <= len(data):
        length = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if length == 0:
            return result, offset
        if length > 128 or offset + length + 4 > len(data):
            raise ValueError("Invalid GIZ section name")
        name = data[offset:offset + length].decode("ascii")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name):
            raise ValueError("Invalid GIZ section identifier")
        offset += length
        size = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if offset + size > len(data):
            raise ValueError("GIZ section exceeds resource bounds")
        result.append(dict(name=name, offset=offset, size=size))
        offset += size
    raise ValueError("Missing GIZ section terminator")


def main() -> None:
    world = Path(__file__).resolve().parents[1]
    analysis = world / "notes/analysis"
    objectives = json.loads((analysis / "candidate_objectives.json").read_text())
    names = {row["definition"]["instanceName"] for row in objectives}
    pattern = re.compile(b"|".join(re.escape(name.encode("ascii")) for name in sorted(names, key=len, reverse=True)))
    rows = []
    matches: dict[str, list[dict]] = collections.defaultdict(list)
    counts = collections.Counter()
    for path in sorted((world / "notes/extracted").rglob("*.giz")):
        data = path.read_bytes()
        relative = path.relative_to(world / "notes/extracted").as_posix()
        row = dict(path=relative, size=len(data), sha256=hashlib.sha256(data).hexdigest())
        if data[:8] == struct.pack("<II", 17, 0):
            blocks, tail = sections(data)
            row.update(status="v17_sections_bounded", sections=blocks, opaque_tail_size=len(data) - tail)
            counts.update(block["name"] for block in blocks)
        else:
            row["status"] = "unsupported_header"
        for match in pattern.finditer(data):
            matches[match.group().decode("ascii")].append(dict(path=relative, byte_offset=match.start(),
                evidence="literal byte substring; runtime activation unverified"))
        rows.append(row)
    (analysis / "gizmo_resources.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (analysis / "objective_resource_evidence.json").write_text(json.dumps(matches, indent=2), encoding="utf-8")
    summary = dict(resources=len(rows), statuses=dict(collections.Counter(row["status"] for row in rows)),
                   section_classes=dict(sorted(counts.items())), scanner_names_found=len(matches))
    (analysis / "gizmo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
