"""Read statically referenced model metadata and nonzero character-state bytes.

State-byte semantics are experimental; this does not claim discovered/purchased/equipped are equivalent.
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
    process = next(r for r in diagnose.diagnose().get("processes", []) if r["status"] == "module_header_read")
    kernel = diagnose.bind_kernel()
    handle = kernel.OpenProcess(0x1010, False, process["pid"])
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        read = lambda address, size: diagnose.read_memory(kernel, handle, address, size)
        pointer = lambda address: struct.unpack("<Q", read(address, 8))[0]
        base = int(process["module_base"], 16)
        manager = pointer(base + 0x17EBD38)
        header = read(manager, 0x120)
        count = struct.unpack_from("<I", header, 0xE0)[0]
        table = struct.unpack_from("<Q", header, 0x118)[0]
        state = pointer(base + 0x1C7CBB8)
        if not 0 < count <= 8192:
            raise ValueError(f"Unexpected model count: {count}")
        flags = b"".join(read(state + 0x80 + i, min(4096, count - i)) for i in range(0, count, 4096))
        discovered = read(state, 128)
        controller = pointer(base + 0x17EBE20)
        control = read(controller + 0x140, 0x70)
        pending = list(struct.unpack_from("<16h", control, 0x2A))
        committed = list(struct.unpack_from("<16h", control, 8))
        extra_pointer = struct.unpack_from("<Q", control, 0x60)[0]
        extra_count = struct.unpack_from("<I", control, 0x6C)[0]
        extras = list(struct.unpack(f"<{extra_count}h", read(extra_pointer, extra_count * 2))) if 0 < extra_count <= 128 else []
        rows = []
        for index, flag in enumerate(flags):
            found = bool(discovered[index // 8] & (1 << (index % 8))) if index < 1024 else False
            if not (flag or found or index in pending or index in committed or index in extras):
                continue
            record = pointer(table + index * 8)
            metadata = read(record, 0x88)
            name_pointer = struct.unpack_from("<Q", metadata, 0x30)[0]
            name = read(name_pointer, 128).split(b"\0", 1)[0].decode("ascii")
            rows.append(dict(index=index, state_byte=flag, name=name,
                             discovered_bit=found, pending_slots=[i for i,x in enumerate(pending) if x==index],
                             committed_slots=[i for i,x in enumerate(committed) if x==index], pending_extra=index in extras,
                             metadata_flags=hex(struct.unpack_from("<I", metadata, 0x24)[0]),
                             model_id=struct.unpack_from("<h", metadata, 8)[0]))
        output = dict(pid=process["pid"], model_count=count, state_pointer=hex(state),
                      model_manager=hex(manager), controller=hex(controller), pending=pending, committed=committed,
                      extras=extras, nonzero_character_states=rows)
        (WORLD / "notes/analysis/live_character_probe.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(json.dumps(output, indent=2))
    finally:
        kernel.CloseHandle(handle)


if __name__ == "__main__":
    main()
