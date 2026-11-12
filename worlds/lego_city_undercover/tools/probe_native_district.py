"""Read native map tile lookup inputs; never call engine functions."""
import ctypes
import json
import math
from pathlib import Path
import struct
import sys

WORLD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD / "bridge"))
import diagnose
from inventory_reader import pointer, cstring


def grid_coordinates(position, origin, cell_size, z_factor, width, height):
    values = (*position, *origin, cell_size, z_factor)
    if not all(math.isfinite(v) for v in values) or cell_size <= 0:
        raise ValueError("Invalid native grid transform")
    if not (0 < width <= 256 and 0 < height <= 256):
        raise ValueError("Invalid native grid dimensions")
    # Reproduce the single-precision arithmetic and truncation in RVA 0x611320.
    f32 = lambda value: struct.unpack("<f", struct.pack("<f", value))[0]
    inverse = f32(1.0 / cell_size)
    x = int(f32(f32(position[0] - origin[0]) * inverse))
    z = int(f32(f32(f32(position[2] - origin[2]) * z_factor) * inverse))
    if not (0 <= x < width and 0 <= z < height):
        raise ValueError("Position outside native grid")
    return x, z


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
        actor = pointer(read, base + 0x1C7D3E0)
        vtable = pointer(read, actor + 0x10)
        if pointer(read, vtable + 0xF0) - base != 0x49ECF0:
            raise ValueError("Unsupported player transform")
        position = struct.unpack("<4f", read(actor + 0x1F0, 16))
        world = pointer(read, base + 0x1C6A768)
        scene = pointer(read, world + 0x178)
        entity = pointer(read, scene + 0x98)
        if pointer(read, pointer(read, entity)) - base != 0x3BE70:
            raise ValueError("Unsupported entity component lookup")
        component_id = struct.unpack("<i", read(base + 0x17EBC30, 4))[0]
        if not 0 <= component_id < 128:
            raise ValueError("Invalid grid component index")
        grid = pointer(read, entity + 0xD0 + component_id * 8)
        nested = pointer(read, grid + 0x38)
        grid = nested or grid
        origin = struct.unpack("<3f", read(grid + 0x100, 12))
        cell_size = struct.unpack("<f", read(grid + 0x110, 4))[0]
        width, height = struct.unpack("<2i", read(base + 0x1165910, 8))
        z_factor = struct.unpack("<f", read(base + 0xC0FE1C, 4))[0]
        x, z = grid_coordinates(position, origin, cell_size, z_factor, width, height)
        table = pointer(read, grid + 0xF0)
        cell = pointer(read, table + (z * width + x) * 8)
        tile = pointer(read, cell + 0x58)
        name = cstring(read, pointer(read, tile + 0x68))
        output = dict(position=position, grid_origin=origin, cell_size=cell_size,
                      grid_dimensions=[width, height], grid_xy=[x, z], z_factor=z_factor,
                      native_tile_name=name, native_tile_coordinates=list(read(tile + 0x208, 2)),
                      map_display_boundary_verified=False)
        if pointer(read, base + 0x1C7D3E0) != actor:
            raise RuntimeError("Player changed during lookup")
        (WORLD / "notes/analysis/live_native_district_probe.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(json.dumps(output, indent=2))
    finally:
        kernel.CloseHandle(handle)


if __name__ == "__main__":
    main()
