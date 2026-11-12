"""Strict parser/round-trip encoder for the supplied JobE 0.1 JobDataMap.

The one-byte field marker is deliberately unnamed: persistence is not yet proven.
This parses game resource defaults, not an actual saved-game file.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import struct

PREFIX = b"JobE\x000.1\x00JobDataMap\x00\x01\x00hEnd\x00<<<<\x00JobDataBlock\x00"
TRAILER = b">>>>\0"


@dataclass(frozen=True)
class Field:
    name: str
    kind: str
    marker: int
    default: int | bool
    source_offset: int = 0


@dataclass(frozen=True)
class Job:
    name: str
    fields: tuple[Field, ...]


class Cursor:
    def __init__(self, data: bytes):
        self.data = data
        self.position = 0

    def take(self, size: int) -> bytes:
        if size < 0 or self.position + size > len(self.data):
            raise ValueError(f"Truncated JobDataMap at {self.position:#x}")
        result = self.data[self.position:self.position + size]
        self.position += size
        return result

    def string(self) -> str:
        end = self.data.find(b"\0", self.position)
        if end < 0 or end - self.position > 1024:
            raise ValueError("Invalid JobDataMap string")
        result = self.take(end - self.position + 1)[:-1].decode("ascii")
        if not result:
            raise ValueError("Empty JobDataMap identifier")
        return result

    def number(self, fmt: str) -> int:
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]


def parse(data: bytes) -> tuple[Job, ...]:
    cursor = Cursor(data)
    if cursor.take(len(PREFIX)) != PREFIX:
        raise ValueError("Unsupported JobDataMap header")
    reserved = cursor.number("<I")
    size = cursor.number("<I")
    start = cursor.position
    if reserved != 0 or start + size + len(TRAILER) != len(data):
        raise ValueError("Invalid JobDataBlock bounds")
    jobs = []
    for _ in range(cursor.number("<H")):
        name = cursor.string()
        fields = []
        for _ in range(cursor.number("<H")):
            source = cursor.position
            field_name, kind = cursor.string(), cursor.string()
            marker = cursor.number("<B")
            if marker not in (0, 1):
                raise ValueError("Unknown field marker")
            if kind == "Bool":
                value = cursor.number("<B")
                if value not in (0, 1):
                    raise ValueError("Invalid Boolean default")
                value = bool(value)
            elif kind == "Int":
                value = cursor.number("<i")
            else:
                raise ValueError(f"Unsupported field type: {kind}")
            fields.append(Field(field_name, kind, marker, value, source))
        if len({field.name for field in fields}) != len(fields):
            raise ValueError(f"Duplicate fields in {name}")
        jobs.append(Job(name, tuple(fields)))
    if len({job.name for job in jobs}) != len(jobs):
        raise ValueError("Duplicate JobDataMap jobs")
    if cursor.position != start + size or cursor.take(len(TRAILER)) != TRAILER:
        raise ValueError("Unexpected JobDataMap block ending")
    return tuple(jobs)


def encode(jobs: tuple[Job, ...]) -> bytes:
    def string(value: str) -> bytes:
        if not value or "\0" in value:
            raise ValueError("Invalid identifier")
        return value.encode("ascii") + b"\0"

    body = bytearray(struct.pack("<H", len(jobs)))
    for job in jobs:
        body.extend(string(job.name) + struct.pack("<H", len(job.fields)))
        for field in job.fields:
            if field.marker not in (0, 1):
                raise ValueError("Invalid field marker")
            body.extend(string(field.name) + string(field.kind) + bytes([field.marker]))
            if field.kind == "Bool" and field.default in (False, True):
                body.extend(bytes([int(field.default)]))
            elif field.kind == "Int":
                body.extend(struct.pack("<i", field.default))
            else:
                raise ValueError("Unsupported field/default")
    result = PREFIX + struct.pack("<II", 0, len(body)) + body + TRAILER
    parse(result)  # Apply the same identifier/type/bounds validation in both directions.
    return result


def main() -> None:
    from dataclasses import asdict
    import collections
    import hashlib

    world = Path(__file__).resolve().parents[1]
    source = world / "notes/extracted/GAME7/jobs/lcu.jobdatamap"
    data = source.read_bytes()
    jobs = parse(data)
    if encode(jobs) != data:
        raise ValueError("JobDataMap round-trip differs")
    fields = [field for job in jobs for field in job.fields]
    output = world / "notes/analysis/job_data.json"
    output.write_text(json.dumps([asdict(job) for job in jobs], indent=2), encoding="utf-8")
    summary = dict(jobs=len(jobs), fields=len(fields), types=dict(collections.Counter(f.kind for f in fields)),
                   markers=dict(collections.Counter(f.marker for f in fields)), sha256=hashlib.sha256(data).hexdigest(),
                   round_trip_exact=True)
    (world / "notes/analysis/job_data_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
