"""Filter the native held-colour query before transformation selection.

8020B444 resolves ordinary Sonic's boost model, then reads its held slot.
Return the native empty value for unowned colours, before state callbacks;
HUD visibility and host inventory polling are not activation authority.
Super's separate native query path remains untouched.
"""
import struct
from .capsule_refresh import PPC

HOOK=0x8020B48C
ORIGINAL=0x80630018


def program(capsule_control,progression_control):
    a=PPC()
    def const(r,v):a.d(15,r,0,v>>16);a.d(24,r,r,v&65535)
    def eq(l,r):a.emit(0x7C000000|l<<16|r<<11)
    a.d(32,0,3,0);const(5,0x80763A18);eq(0,5);a.branch('vanilla',0x40820000)
    a.emit(ORIGINAL)
    a.d(10,0,3,6);a.branch('done',0x41810000)  # includes empty -1
    const(12,capsule_control);a.d(32,5,12,0)
    a.d(11,0,5,0);a.branch('done',0x41820000)  # inactive AP policy
    a.d(34,0,5,0);a.d(32,6,12,4);eq(0,6);a.branch('deny',0x40820000)
    a.d(10,0,6,3);a.branch('deny',0x41810000)
    const(12,0x19608);a.emit(0x7CC661D6)
    a.d(14,6,6,0x24);a.emit(0x7CA53214)
    const(12,progression_control);a.d(32,0,12,0);eq(0,5);a.branch('deny',0x40820000)
    a.d(14,6,0,1);a.emit(0x7CC61830)  # slw r6,r6,r3
    a.d(32,0,12,8);a.emit(0x7C003039);a.branch('done',0x40820000)
    a.label('deny');a.d(14,3,0,-1);a.branch('done')
    a.label('vanilla');a.emit(ORIGINAL)
    a.label('done');a.emit(0)
    return a.finish()


def patches(capsule_control,progression_control,occupied):
    from ..world_constants import load_data
    from .native_dol import branch
    from .native_events import scatter
    sites=load_data('wisp_activation_sites.json')
    for s in sites:
        if any(s['address']<a+len(n) and a<s['address']+12 for a,o,n in occupied):
            raise ValueError('Wisp activation padding overlaps another hook')
    return [(HOOK,struct.pack('>I',ORIGINAL),struct.pack('>I',branch(HOOK,sites[0]['address']))),
            *scatter(program(capsule_control,progression_control),sites,HOOK+4,compact=True)]


def planned_patches():
    from .native_dol import plan
    rows=plan()[0];start=next(i for i,row in enumerate(rows) if row[0]==HOOK)
    from .native_events import scatter
    from ..world_constants import load_data
    count=len(scatter(program(0,0),load_data('wisp_activation_sites.json'),HOOK+4,compact=True))
    return rows[start:start+1+count]
