"""Read the statically referenced job registry and selected story variable objects.

Development probe only. All binary evidence is written under ignored notes/analysis.
"""
from __future__ import annotations

import ctypes
import json
from pathlib import Path
import struct
import sys

WORLD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD / "bridge"))
import diagnose
from inventory_reader import pointer
from research_profile import symbol_hash


def main() -> None:
    process = next(r for r in diagnose.diagnose().get("processes", []) if r["status"] == "module_header_read")
    kernel = diagnose.bind_kernel()
    handle = kernel.OpenProcess(0x1010, False, process["pid"])
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        read = lambda address, size: diagnose.read_memory(kernel, handle, address, size)
        base = int(process["module_base"], 16)
        manager = pointer(read, base + 0x17ECA08)
        header = read(manager + 0xE0, 16)
        table, count = struct.unpack_from("<QI", header)
        if not 0 <= count <= 4096:
            raise ValueError(f"Unexpected job count {count}")
        raw = b"".join(read(table + i, min(4096, count * 24 - i)) for i in range(0, count * 24, 4096))
        expected = json.loads((WORLD / "notes/analysis/job_data.json").read_text())
        known = {symbol_hash(row["name"]): row for row in expected}
        rows = []
        for i in range(count):
            job_hash, fields_pointer, field_count = struct.unpack_from("<I4xQH", raw, i * 24)
            definition = known.get(job_hash)
            if not definition or not (definition["name"].startswith("Flow_Setup") or "LCPD" in definition["name"]):
                continue
            if field_count > 128:
                raise ValueError("Unexpected field count")
            names = {symbol_hash(field["name"]): field for field in definition["fields"]}
            objects = read(fields_pointer, field_count * 8) if field_count else b""
            fields = []
            for j in range(field_count):
                obj = struct.unpack_from("<Q", objects, j * 8)[0]
                data = read(obj, 32)
                vtable, name_hash = struct.unpack_from("<Q4xI", data)
                getter = pointer(read, vtable + 8)
                field = names.get(name_hash)
                fields.append(dict(name=field["name"] if field else None, expected_type=field["kind"] if field else None,
                                   hash=name_hash, raw_hex=data.hex(), getter_rva=hex(getter - base),
                                   object_pointer=hex(obj), vtable_rva=hex(vtable - base)))
            rows.append(dict(name=definition["name"], fields=fields))
        output = dict(pid=process["pid"], job_count=count, manager=hex(manager), jobs=rows)
        (WORLD / "notes/analysis/live_story_probe.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(json.dumps(dict(job_count=count, selected_jobs=len(rows),
                              getter_rvas=sorted({f["getter_rva"] for row in rows for f in row["fields"]})), indent=2))
    finally:
        kernel.CloseHandle(handle)


if __name__ == "__main__":
    main()
