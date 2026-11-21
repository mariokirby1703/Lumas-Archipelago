"""Native tile lookup for monitor context. Source-region names are not map labels."""
import math
import struct
from inventory_reader import pointer, cstring


def read_location(read, base):
    actor = pointer(read, base + 0x1C7D3E0)
    if not actor:return dict(area_status='not_initialized')
    interface=pointer(read,actor+0x10)
    if not interface:return dict(area_status='not_initialized')
    getter = pointer(read, interface + 0xF0) - base
    if getter != 0x49ECF0:
        raise ValueError('Unsupported player transform')
    pos = struct.unpack('<4f', read(actor + 0x1F0, 16))
    result = dict(player_position=list(pos[:3]), area_status='unresolved')
    world = pointer(read, base + 0x1C6A768)
    if not world:return dict(result,reason='city_world_not_initialized')
    scene = pointer(read, world + 0x178)
    if not scene:return dict(result,reason='city_scene_not_initialized')
    entity = pointer(read, scene + 0x98)
    if not entity:return dict(result,reason='city_entity_not_initialized')
    entity_type=pointer(read,entity)
    if not entity_type or pointer(read, entity_type) - base != 0x3BE70:
        return result
    index = struct.unpack('<i', read(base + 0x17EBC30, 4))[0]
    if not 0 <= index < 128:
        return result
    grid = pointer(read, entity + 0xD0 + index * 8)
    if not grid:
        return result
    grid = pointer(read, grid + 0x38) or grid
    origin = struct.unpack('<3f', read(grid + 0x100, 12))
    size = struct.unpack('<f', read(grid + 0x110, 4))[0]
    factor = struct.unpack('<f', read(base + 0xC0FE1C, 4))[0]
    width, height = struct.unpack('<2i', read(base + 0x1165910, 8))
    if not all(math.isfinite(v) for v in (*pos, *origin, size, factor)) or size <= 0:
        return result
    f32 = lambda v: struct.unpack('<f', struct.pack('<f', v))[0]
    inverse = f32(1.0 / size)
    fx=f32(f32(pos[0] - origin[0]) * inverse)
    fz=f32(f32(f32(pos[2] - origin[2]) * factor) * inverse)
    if not (0 <= fx < width <= 256 and 0 <= fz < height <= 256):
        return result
    x,z=int(fx),int(fz)
    cells=pointer(read,grid+0xF0)
    if not cells:return dict(result,reason='city_grid_not_initialized')
    cell = pointer(read, cells + (z*width+x)*8)
    if not cell:return dict(result,reason='city_cell_not_loaded')
    tile = pointer(read, cell + 0x58)
    if not tile:return dict(result,reason='city_tile_not_loaded')
    name_pointer=pointer(read,tile+0x68)
    if not name_pointer:return dict(result,reason='city_tile_name_not_loaded')
    name = cstring(read,name_pointer)
    if pointer(read, base + 0x1C7D3E0) != actor:
        raise RuntimeError('Player changed during position read')
    result.update(native_tile=name, area_status='native_tile', grid_xy=[x,z])
    return result
