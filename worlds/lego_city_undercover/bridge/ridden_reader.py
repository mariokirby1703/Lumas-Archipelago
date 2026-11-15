"""Read the reviewed Character_GetRidden accessor chain without executing it."""
import math
import struct
from inventory_reader import pointer


def read_ridden(read,base):
    actor=pointer(read,base+0x1c7d3e0)
    if not actor:return dict(status='not_loaded')
    component=pointer(read,actor+0x340)
    controller=pointer(read,component+0x88) if component else 0
    if not controller:return dict(status='not_riding')
    getter=pointer(read,pointer(read,controller)+0x240)
    if getter!=base+0x1f8830:return dict(status='unreviewed_ridden_accessor',getter_rva=hex(getter-base))
    target=pointer(read,controller+0x20)
    if not target or target==actor:return dict(status='not_riding')
    if pointer(read,pointer(read,target+0x10)+0xf0)!=base+0x49ecf0:
        return dict(status='unsupported_creature_transform',target=hex(target))
    position=struct.unpack('<4f',read(target+0x1f0,16))
    if not all(math.isfinite(v) for v in position) or abs(position[3]-1)>0.001:
        raise ValueError('Invalid ridden character transform')
    if pointer(read,controller+0x20)!=target or pointer(read,base+0x1c7d3e0)!=actor:
        raise RuntimeError('Ridden character changed during snapshot')
    return dict(status='native_ridden_character',target=hex(target),position=list(position[:3]),
                source='Character_GetRidden / MechCharacterBaseInterface+20',species='not_inferred')
