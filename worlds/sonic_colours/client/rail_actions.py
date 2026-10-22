"""Gate native grind input decisions before jump/switch side effects.

800CA244 handles side actions 2/3; 800CA2C4 handles both action 0 and
8020B1E0's alternate jump trigger. Returning false keeps the native grind
update running on its current rail, instead of ejecting or reattaching Sonic.
"""
import struct
from .capsule_refresh import PPC

HOOKS={'switch':(0x800CA244,0x9421FFF0,1024),
       'jump':(0x800CA2C4,0x9421FFF0,512)}
GRIND_VTABLE=0x80760AC4


def program(kind,control):
    a=PPC()
    def const(r,v):a.d(15,r,0,v>>16);a.d(24,r,r,v&65535)
    def eq(l,r):a.emit(0x7C000000|l<<16|r<<11)
    a.d(37,1,1,-0x20)
    for r in range(9,13):a.d(36,r,1,8+(r-9)*4)
    const(12,control);a.d(32,9,12,0);a.d(11,0,9,0);a.branch('allow',0x41820000)
    a.d(32,9,3,0);const(10,GRIND_VTABLE);eq(9,10);a.branch('allow',0x40820000)
    a.d(32,9,4,0);const(10,0x8075A0F8);eq(9,10);a.branch('allow',0x40820000)
    a.d(32,11,4,0x28);a.d(11,0,11,0);a.branch('allow',0x41820000)
    a.d(32,9,11,0);const(10,0x8075AEF8);eq(9,10);a.branch('allow',0x40820000)
    a.d(32,10,11,0x70);a.d(11,0,10,0);a.branch('allow',0x41820000)
    a.d(32,10,10,8);eq(10,4);a.branch('allow',0x40820000)
    a.d(14,10,0,HOOKS[kind][2])
    if kind=='jump':
        # Native short jumps can become directional rail transfers. Check
        # currently held side actions as well, independent of press cadence.
        a.d(32,9,11,0x88);a.d(11,0,9,0);a.branch('allow',0x41820000)
        a.d(32,9,9,0x4c);a.d(28,9,9,0xc);a.branch('permission',0x41820000)
        a.d(24,10,10,1024)
    a.label('permission');a.d(32,9,12,4);a.emit(0x7D295039);eq(9,10)
    a.branch('allow',0x41820000)
    # The helper reports 'no action' without changing rail ownership, native
    # input buffers, jump flags, velocity or pending death/scripted requests.
    a.d(14,3,0,0);a.branch('deny')
    a.label('allow')
    def restore():
        for r in range(9,13):a.d(32,r,1,8+(r-9)*4)
        a.d(14,1,1,0x20)
    restore();a.emit(HOOKS[kind][1]);allowed=len(a.words);a.branch('native_return')
    a.label('deny');restore();a.emit(0x4E800020)
    a.label('native_return');a.emit(0)
    return a.finish(),allowed


def patches(control,occupied):
    from ..world_constants import load_data
    from .native_dol import branch
    from .native_events import scatter
    sites=load_data('rail_action_sites.json');result=[];used=0
    for kind,(hook,original,_) in HOOKS.items():
        words,allowed=program(kind,control);selected=sites[used:]
        chunks=scatter(words,selected,hook+4,compact=True)
        result.append((hook,struct.pack('>I',original),struct.pack('>I',branch(hook,selected[0]['address']))))
        result.extend(chunks);used+=len(chunks)
    if any(a<e+len(n) and e<a+len(new) for a,o,new in result for e,old,n in occupied):
        raise ValueError('Rail action code overlaps another patch')
    return result


def planned_patches():
    from .native_dol import plan
    rows=plan()[0];start=next(i for i,r in enumerate(rows) if r[0]==HOOKS['switch'][0])
    return rows[start:start+len(patches(0,[]))]
