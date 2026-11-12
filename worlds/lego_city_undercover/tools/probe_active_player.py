"""Read the statically referenced active player handle and its virtual accessor.

Does not invoke game functions or write game memory.
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
from inventory_reader import pointer, cstring


def main() -> None:
    process = next(r for r in diagnose.diagnose().get("processes", []) if r["status"] == "module_header_read")
    kernel = diagnose.bind_kernel()
    handle = kernel.OpenProcess(0x1010, False, process["pid"])
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        read = lambda address, size: diagnose.read_memory(kernel, handle, address, size)
        base = int(process["module_base"], 16)
        player = pointer(read, base + 0x1C7D3E0)
        entity_ref = player + 0x10
        vtable = pointer(read, entity_ref)
        getter = pointer(read, vtable + 0x1E0)
        accessor = dict(player=hex(player), getter_rva=hex(getter-base), getter_bytes=read(getter, 32).hex())
        (WORLD / "notes/analysis/live_character_accessor.json").write_text(json.dumps(accessor, indent=2), encoding="utf-8")
        if getter - base != 0x6697D0:
            raise ValueError("Unexpected character accessor")
        character = player
        type_flags = struct.unpack("<I", read(character + 0xD4, 4))[0]
        if not type_flags & 0x1000:
            raise ValueError(f"Root is not a character: {type_flags:#x}")
        model = pointer(read, character + 0x650)
        model_name = cstring(read, pointer(read, model + 0x30))
        items = pointer(read, character + 0x8A0)
        node = pointer(read, items + 0x90) if items else 0
        item_rows = []
        seen = set()
        while node and len(item_rows) < 128:
            if node in seen:
                raise ValueError("Cyclic item list")
            seen.add(node)
            row = read(node, 0x30)
            definition = struct.unpack_from("<Q", row, 0x10)[0]
            item_rows.append(dict(node=hex(node), definition=hex(definition),
                                  name=cstring(read, definition + 0x58), raw_hex=row.hex()))
            node = struct.unpack_from("<Q", row, 8)[0]
        output = dict(player=hex(player), entity_ref=hex(entity_ref), getter_rva=hex(getter-base),
                      character=hex(character),
                      model_name=model_name, item_controller=hex(items), items=item_rows)
        (WORLD / "notes/analysis/live_active_player_probe.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(json.dumps(output, indent=2))
    finally:
        kernel.CloseHandle(handle)


if __name__ == "__main__":
    main()
