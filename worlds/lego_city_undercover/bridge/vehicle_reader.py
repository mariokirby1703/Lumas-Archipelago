"""Read Character_GetVehicle's weak reference, without acquiring/calling it."""
import math
import struct
import json
from pathlib import Path
from inventory_reader import pointer

VEHICLE_TYPES=json.loads((Path(__file__).with_name('vehicle_types.json')).read_text(encoding='utf-8'))
RAIL_MODELS=frozenset(('courser','cydonia','cydoniacarriage','cydoniarear',
                      'emeraldnight_cab','emeraldnight_carriage1','emeraldnight_carriage2'))


def read_ride(read,base):
    actor=pointer(read,base+0x1c7d3e0)
    if not actor:return dict(status='not_loaded')
    pair=read(actor+0x428,16);weak,control=struct.unpack('<2Q',pair)
    if not weak and not control:return dict(status='not_mounted')
    if not weak or not control:return dict(status='unresolved_weak_reference')
    alive=struct.unpack('<i',read(control+4,4))[0]
    if alive<=0:return dict(status='expired_weak_reference')
    ride=pointer(read,weak)
    if not ride:return dict(status='empty_vehicle_reference')
    vtable=pointer(read,ride)
    getter=pointer(read,vtable+0xf0)-base
    result=dict(status='unsupported_transform',vehicle_interface=hex(ride),weak_control=hex(control),getter_rva=hex(getter))
    known=VEHICLE_TYPES.get(hex(vtable-base))
    if known:
        result.update(native_class=known['native_class'],vtable_rva=hex(vtable-base),
                      setter_rva=hex(pointer(read,vtable+0xf8)-base))
        # Vehicle_GetModelName 1193d0 -> 45d2c0, bounded string read.
        definition=pointer(read,ride+0x358)
        helper=pointer(read,definition+0x58) if definition else 0
        block=pointer(read,helper+0x48) if helper else 0
        text=pointer(read,block+0x20) if block else 0
        if text:
            raw=read(text,128)
            if b'\0' in raw:
                name=raw.split(b'\0',1)[0].decode('ascii')
                result.update(model_name=name,rail_transport=name.casefold() in RAIL_MODELS)
        # Vehicle_GetDriver -> 4b8450(vehicle, 1): bounded occupant list.
        seat=pointer(read,ride+0x580);seen=set()
        for _ in range(32):
            if not seat or seat in seen:break
            seen.add(seat)
            kind,flags=struct.unpack('<2B',read(seat+0x3c,2))
            if kind==1:
                driver=pointer(read,seat+0x20) if flags&1 else 0
                result['player_role']='driver' if driver==actor+0x10 else 'passenger' if driver else 'unknown'
                break
            seat=pointer(read,seat+8)
    transform = ride + 0x50 if getter == 0x506fe0 else None
    physics = pointer(read,ride+0x348) if getter == 0x4a9370 else 0
    if physics:
        transform = physics + 0x60
    if transform is not None:
        position=struct.unpack('<4f',read(transform+0x30,16))
        if not all(math.isfinite(v) for v in position):raise ValueError('Invalid vehicle transform')
        result.update(status='native_physics_vehicle_transform' if physics else 'native_base_vehicle_transform',position=list(position[:3]))
    if (pointer(read,base+0x1c7d3e0)!=actor or read(actor+0x428,16)!=pair or pointer(read,weak)!=ride or pointer(read,ride)!=vtable or
        struct.unpack('<i',read(control+4,4))[0]<=0):raise RuntimeError('Vehicle changed during snapshot')
    return result
