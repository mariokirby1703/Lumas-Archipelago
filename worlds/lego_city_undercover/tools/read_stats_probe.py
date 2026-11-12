"""Capture only statically referenced stats fields from the supported local game.

Read-only development probe; raw output remains in ignored notes/analysis.
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


def main() -> None:
    result = diagnose.diagnose()
    process = next((r for r in result.get("processes", []) if r["status"] == "module_header_read"), None)
    if process is None:
        raise RuntimeError("Supported running process required")
    kernel = diagnose.bind_kernel()
    handle = kernel.OpenProcess(0x1010, False, process["pid"])
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        read = lambda address, size: diagnose.read_memory(kernel, handle, address, size)
        base = int(process["module_base"], 16)
        manager = struct.unpack("<Q", read(base + 0x1C7A830, 8))[0]
        data = read(manager + 0x3300, 0x3A0)
        rows = [dict(offset=hex(0x3300 + off), u32=struct.unpack_from("<I", data, off)[0],
                     f32=struct.unpack_from("<f", data, off)[0]) for off in range(0, len(data), 4)]
        profile = struct.unpack("<Q", read(base + 0x1C7F160, 8))[0]
        profile_studs = struct.unpack("<Q", read(profile + 0xFB10, 8))[0]
        output = dict(pid=process["pid"], manager=hex(manager), raw_hex=data.hex(), fields=rows,
                      profile_pointer=hex(profile), profile_studs_candidate=profile_studs)
        (WORLD / "notes/analysis/live_stats_probe.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(json.dumps(dict(profile_studs_candidate=profile_studs,
                             selected=[row for row in rows if row["offset"] in ("0x3314", "0x3318", "0x3348", "0x3664")]), indent=2))
    finally:
        kernel.CloseHandle(handle)


if __name__ == "__main__":
    main()
