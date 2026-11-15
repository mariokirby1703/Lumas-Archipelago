"""Read Character_GetVehicle's weak reference, without acquiring/calling it."""
import math
import struct
from inventory_reader import pointer


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
    getter=pointer(read,pointer(read,ride)+0xf0)-base
    result=dict(status='unsupported_transform',vehicle_interface=hex(ride),weak_control=hex(control),getter_rva=hex(getter))
    if getter==0x506fe0:
        position=struct.unpack('<4f',read(ride+0x80,16))
        if not all(math.isfinite(v) for v in position):raise ValueError('Invalid vehicle transform')
        result.update(status='native_base_vehicle_transform',position=list(position[:3]))
    if (pointer(read,base+0x1c7d3e0)!=actor or read(actor+0x428,16)!=pair or pointer(read,weak)!=ride or
        struct.unpack('<i',read(control+4,4))[0]<=0):raise RuntimeError('Vehicle changed during snapshot')
    return result
