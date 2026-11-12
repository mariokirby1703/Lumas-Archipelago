"""Capture the statically identified 1,600-byte city-pickup save payload read-only.

Individual byte semantics remain unverified. Never invokes native save methods.
"""
import ctypes
import hashlib
import json
from pathlib import Path
import struct
import sys

from pickup_save_data import extract_section, set_bits

WORLD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD / "bridge"))
import diagnose
from inventory_reader import pointer


def main():
    process = next(p for p in diagnose.diagnose()["processes"] if p["status"] == "module_header_read")
    if process["sha256"] != diagnose.RESEARCH_HASH:
        raise ValueError("Unsupported executable")
    kernel = diagnose.bind_kernel()
    handle = kernel.OpenProcess(0x1010, False, process["pid"])
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        read = lambda address, size: diagnose.read_memory(kernel, handle, address, size)
        base = int(process["module_base"], 16)
        manager = pointer(read, base + 0x17EC808)
        if not manager:
            raise ValueError("Pickup manager not initialized")
        payload = read(manager + 0x120, 1600)
        if len(payload) != 1600 or read(manager + 0x120, 1600) != payload:
            raise RuntimeError("Pickup payload changed during capture")
        if pointer(read, base + 0x17EC808) != manager:
            raise RuntimeError("Pickup manager changed during capture")
        analysis = WORLD / "notes/analysis"
        (analysis / "live_pickup_save_payload.bin").write_bytes(payload)
        slots = struct.unpack("<800H", payload)
        output = dict(manager_vtable_rva=hex(pointer(read, manager)-base),
                      payload_size=len(payload), sha256=hashlib.sha256(payload).hexdigest(),
                      nonzero_u16_slots={str(i): value for i, value in enumerate(slots) if value},
                      interpretation="opaque payload; u16 view is diagnostic only",
                      raw_set_bit_offsets=set_bits(payload),
                      persistent_ids_verified=False)
        backups = sorted((WORLD / "notes/save_backups").glob("slot1_*/game1.*"))
        output["exact_save_matches"] = []
        output["save_sections"] = []
        for path in backups:
            data = path.read_bytes()
            offset, saved = extract_section(data)
            output["save_sections"].append(dict(backup=path.parent.name, offset=offset,
                                                raw_set_bit_offsets=set_bits(saved),
                                                matches_live_payload=saved == payload))
            start = 0
            while (hit := data.find(payload, start)) >= 0:
                output["exact_save_matches"].append(dict(backup=path.parent.name, offset=hit))
                start = hit + 1
        (analysis / "live_pickup_save_probe.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(json.dumps(output, indent=2))
    finally:
        kernel.CloseHandle(handle)


if __name__ == "__main__":
    main()
