"""Conservative, read-only catalogue of bounded v14 GizmoPickup records.

Coordinates are resource coordinates. Keys identify source records, not save bits.
Unsupported layouts are reported and never partially admitted to the catalogue.
"""
from __future__ import annotations

import collections
import csv
import json
import math
from pathlib import Path
import struct

from resource_catalogue import sections

TYPE_LABELS = {80: "Gold Plate", 106: "SuperBrick4X2"}


def parse_pickups(data: bytes) -> list[dict]:
    if len(data) < 36:
        raise ValueError("Truncated pickup header")
    version, count = struct.unpack_from("<II", data)
    if version not in (13,14) or count > 100000:
        raise ValueError("Unsupported pickup header")
    offset = 36
    rows = []
    type_size=4 if version==14 else 3
    prefix_size=type_size+7
    for index in range(count):
        if offset + prefix_size > len(data):
            raise ValueError("Truncated pickup prefix")
        start = offset
        type_word=int.from_bytes(data[offset:offset+type_size],'little')
        reference,flags=struct.unpack_from('<hI',data,offset+type_size)
        length = data[offset + prefix_size-1]
        offset += prefix_size
        if not length or offset + length + 22 > len(data):
            raise ValueError("Invalid pickup name bounds")
        raw = data[offset:offset + length]
        if raw[-1] != 0 or any(c < 32 or c > 126 for c in raw[:-1]):
            raise ValueError("Invalid pickup name")
        offset += length
        xyz = struct.unpack_from("<3f", data, offset)
        if not all(math.isfinite(v) for v in xyz):
            raise ValueError("Nonfinite pickup position")
        offset += 12
        tail = data[offset:offset + 10]
        offset += 10
        parent=None
        if tail[8]==1:
            size=tail[9]
            if not size or offset+size+13>len(data):raise ValueError('Invalid pickup parent bounds')
            parent_raw=data[offset:offset+size]
            if parent_raw[-1]!=0 or any(c<32 or c>126 for c in parent_raw[:-1]):
                raise ValueError('Invalid pickup parent name')
            local_xyz=struct.unpack_from('<3f',data,offset+size)
            if not all(math.isfinite(v) for v in local_xyz):raise ValueError('Invalid parent coordinates')
            parent=dict(name=parent_raw[:-1].decode('ascii'),local_xyz=list(local_xyz),
                        trailing_byte=data[offset+size+12])
            offset+=size+13
        elif tail[8] or tail[9]:raise ValueError('Unrecognized pickup parent extension')
        rows.append(dict(index=index, section_offset=start, type_word=type_word,
                         type_code=type_word & 255, reference=reference, flags=flags,
                         name=raw[:-1].decode("ascii"), resource_xyz=list(xyz),
                         opaque_tail=tail.hex(),parent=parent))
    if offset != len(data):
        raise ValueError("Unrecognized pickup record extension")
    return rows


def main() -> None:
    world = Path(__file__).resolve().parents[1]
    root = world / "notes/extracted"
    rows, rejected = [], []
    for path in sorted(root.rglob("*.giz")):
        data = path.read_bytes()
        try:
            blocks, _ = sections(data)
        except ValueError:
            continue
        resource = path.relative_to(root).as_posix()
        for block in blocks:
            if block["name"] != "GizmoPickup":
                continue
            try:
                parsed = parse_pickups(data[block["offset"]:block["offset"] + block["size"]])
            except ValueError as error:
                rejected.append(dict(resource=resource, section_offset=block["offset"], reason=str(error)))
                continue
            for row in parsed:
                row.update(resource=resource, source_key=f"{resource}:{block['offset']}:{row['index']}")
                if row["type_code"] in TYPE_LABELS:
                    row["native_type_label"] = TYPE_LABELS[row["type_code"]]
                rows.append(row)
    bricks = [r for r in rows if r["type_code"] in TYPE_LABELS]
    city = [r for r in bricks if "/levels/lego_city/lego_city/" in r["resource"]]
    report = dict(records=len(rows), superbrick_candidates=len(bricks),
                  city_resource_records=len(city),
                  types=dict(collections.Counter(r["native_type_label"] for r in bricks)),
                  rejected_sections=rejected, resource_coordinates_only=True,
                  persistent_collection_ids_verified=False)
    analysis = world / "notes/analysis"
    for name, content in (("pickup_catalogue.json", rows), ("superbrick_catalogue.json", bricks),
                          ("pickup_catalogue_summary.json", report)):
        (analysis / name).write_text(json.dumps(content, indent=2), encoding="utf-8")
    with (analysis / "city_superbricks.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("source_key", "resource_district", "name", "type", "x", "y", "z"))
        for row in city:
            district = row["resource"].split("/levels/lego_city/lego_city/", 1)[1].split("/", 1)[0]
            writer.writerow((row["source_key"], district, row["name"], row["native_type_label"], *row["resource_xyz"]))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
