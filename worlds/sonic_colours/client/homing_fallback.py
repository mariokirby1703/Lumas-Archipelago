"""Let the native air-action helper try Double Jump when Homing is locked.

80097790 normally returns after the selected homing request, even if the AP
dispatcher rejects it. Returning the selector's native 'no action' result here
keeps 800919CC/8020D1C0 and their one-use/airborne checks in charge. Never
redirect a state request to Double Jump or reset its native availability.
"""
import struct
from .capsule_refresh import PPC

HOOK=0x800977D0
ORIGINAL=0x2C03FFFF  # cmpwi r3,-1


def program(control):
    a=PPC()
    def const(r,value):a.d(15,r,0,value>>16);a.d(24,r,r,value&65535)
    def eq(l,r):a.emit(0x7C000000|l<<16|r<<11)
    a.d(37,1,1,-0x20)
    for r in range(9,13):a.d(36,r,1,8+(r-9)*4)
    a.d(11,0,3,13);a.branch('done',0x40820000)
    const(12,control);a.d(32,9,12,0);a.d(11,0,9,0);a.branch('done',0x41820000)
    # r29 is the native action context; +28 owns Sonic's actual actor.
    a.d(32,11,29,0x28);a.d(11,0,11,0);a.branch('done',0x41820000)
    a.d(32,9,11,0);const(10,0x8075AEF8);eq(9,10);a.branch('done',0x40820000)
    a.d(32,10,11,0x70);a.d(11,0,10,0);a.branch('done',0x41820000)
    a.d(32,10,10,8);a.d(11,0,10,0);a.branch('done',0x41820000)
    a.d(32,9,10,0);const(12,0x8075A0F8);eq(9,12);a.branch('done',0x40820000)
    a.d(32,9,10,0x28);eq(9,11);a.branch('done',0x40820000)
    const(12,control);a.d(32,9,12,4);a.d(28,9,9,4);a.branch('done',0x40820000)
    a.d(14,3,0,-1)
    a.label('done')
    for r in range(9,13):a.d(32,r,1,8+(r-9)*4)
    a.d(14,1,1,0x20);a.emit(ORIGINAL);a.emit(0)
    return a.finish()


def patches(control,occupied):
    from ..world_constants import load_data
    from .native_dol import branch
    from .native_events import scatter
    sites=load_data('homing_fallback_sites.json')
    if any(s['address']<a+len(new) and a<s['address']+12 for s in sites for a,old,new in occupied):
        raise ValueError('Homing fallback padding overlaps another native patch')
    return [(HOOK,struct.pack('>I',ORIGINAL),struct.pack('>I',branch(HOOK,sites[0]['address']))),
            *scatter(program(control),sites,HOOK+4)]


def planned_patches():
    from .native_dol import plan
    rows=plan()[0];start=next(i for i,row in enumerate(rows) if row[0]==HOOK)
    return rows[start:start+1+len(program(0))]
