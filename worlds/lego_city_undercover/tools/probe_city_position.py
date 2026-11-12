"""Read-only position accessor and city district registry research probe."""
import ctypes
import json
from pathlib import Path
import struct
import sys

WORLD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD / "bridge"))
import diagnose
from inventory_reader import pointer


def main():
    process = next(p for p in diagnose.diagnose()["processes"] if p["status"] == "module_header_read")
    if process.get("sha256") != diagnose.RESEARCH_HASH:
        # diagnose uses a different field name in some diagnostic revisions.
        import hashlib
        if hashlib.sha256(Path(process["path"]).read_bytes()).hexdigest() != diagnose.RESEARCH_HASH:
            raise ValueError("Unsupported executable")
    kernel = diagnose.bind_kernel()
    handle = kernel.OpenProcess(0x1010, False, process["pid"])
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        read = lambda address, size: diagnose.read_memory(kernel, handle, address, size)
        base = int(process["module_base"], 16)
        actor = pointer(read, base + 0x1C7D3E0)
        vtable = pointer(read, actor + 0x10)
        getter = pointer(read, vtable + 0xF0) - base
        output = dict(transform_getter_rva=hex(getter), current_district_verified=False)
        if getter == 0x506FE0:
            output["actor_position_xyzw"] = struct.unpack("<4f", read(actor + 0x90, 16))
        elif getter == 0x49ECF0:
            output["actor_position_xyzw"] = struct.unpack("<4f", read(actor + 0x1F0, 16))
        manager = pointer(read, base + 0x17ECA20)
        output["district_registry_initialized"] = bool(manager)
        if manager:
            output["district_record_values_at_4"] = [struct.unpack("<I", read(manager + 0xE4 + i * 0x28, 4))[0]
                                                 for i in range(23)]
        if pointer(read, base + 0x1C7D3E0) != actor:
            raise RuntimeError("Player changed during snapshot")
        (WORLD / "notes/analysis/live_city_position_probe.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(json.dumps(output, indent=2))
    finally:
        kernel.CloseHandle(handle)


if __name__ == "__main__":
    main()
