"""Read the active character's native level component table without calls."""
import struct
from inventory_reader import pointer


def player_scene(read, base):
    actor = pointer(read, base + 0x1C7D3E0)
    if not actor:
        raise ValueError('Spieler nicht geladen')
    interface = pointer(read, actor + 0x10)
    if pointer(read, interface + 0x10) != base + 0x487160:
        raise ValueError('Unbekannter Szenen-Accessor')
    index = struct.unpack('<H', read(actor + 0x28, 2))[0]
    if index > 0x7FF:
        raise ValueError('Ungültige Spieler-Szenenkennung')
    registry = pointer(read, base + 0x1C402D8)
    entry = pointer(read, registry + 0x18 + index*8)
    owner = pointer(read, entry + 0xD8)
    if not pointer(read, owner + 0xB18):
        raise ValueError('Keine geladene Spielerszene')
    level = pointer(read, owner + 0xBB0)
    data = pointer(read, level + 0xA0)
    table = pointer(read, data + 0xC0)
    if not table or pointer(read, base + 0x1C7D3E0) != actor:
        raise RuntimeError('Spielerszene wechselte')
    return dict(actor=actor, level=level, table=table)


def scene_component(read, base, scene, global_rva):
    manager = pointer(read, base + global_rva)
    index = struct.unpack('<i', read(manager + 0xF4, 4))[0]
    if not 0 <= index < 256:
        raise ValueError('Ungültiger Szenenkomponentenindex')
    return pointer(read, scene['table'] + index*8)
