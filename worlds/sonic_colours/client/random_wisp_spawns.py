"""Filter each multi-capsule Wisp before its allocation and scene insertion.

Only the five ReleaseBoxSmall multi/random spawn callsites are intercepted.
The normal capsule opening, its successful-opening check, and other actors'
spawn routines remain native. Each allowed colour keeps its original motion.
"""
import struct
from .capsule_refresh import PPC

SPAWN=0x800FD6C0
HOOKS=(0x800D4D8C,0x800D4DC8,0x800D4E28,0x800D4E5C,0x800D4E90)


def program(capsule_control,progression_control):
    a=PPC()
    def const(r,v):a.d(15,r,0,v>>16);a.d(24,r,r,v&65535)
    def eq(l,r):a.emit(0x7C000000|l<<16|r<<11)
    # r3 scene, r4 native spawn args: +20 is the requested native colour.
    # Only volatile scratch registers change. Original BL return LR, r3/r4,
    # FPRs, stack and nonvolatile registers survive our tail dispatch.
    a.d(32,7,4,0x20);a.d(10,0,7,6);a.branch('spawn',0x41810000)
    const(12,capsule_control);a.d(32,5,12,0)
    a.d(11,0,5,0);a.branch('spawn',0x41820000)
    a.d(34,0,5,0);a.d(32,6,12,4);eq(0,6);a.branch('deny',0x40820000)
    a.d(10,0,6,3);a.branch('deny',0x41810000)
    const(12,0x19608);a.emit(0x7CC661D6)
    a.d(14,6,6,0x24);a.emit(0x7CA53214)
    const(12,progression_control);a.d(32,0,12,0);eq(0,5);a.branch('deny',0x40820000)
    a.d(14,6,0,1);a.emit(0x7CC63830)  # slw r6,r6,r7
    a.d(32,0,12,8);a.emit(0x7C003039);a.branch('spawn',0x40820000)
    a.label('deny');a.emit(0x4e800020)  # no allocation or scene insertion
    a.label('spawn');a.emit(0)  # tail-call the original spawn using original BL LR
    return a.finish()


def patches(capsule_control,progression_control,occupied):
    from ..world_constants import load_data
    from .native_dol import branch
    sites=load_data('random_wisp_spawn_sites.json');words=program(capsule_control,progression_control)
    if len(words)!=len(sites):raise ValueError('Random Wisp spawn layout differs')
    result=[]
    for i,word in enumerate(words):
        s=sites[i];a=s['address'];following=sites[i+1]['address'] if i+1<len(sites) else SPAWN
        if i==len(words)-1:chunk=[branch(a,SPAWN),0x60000000]
        elif word>>26 in (16,18):
            op=word>>26;mask,sign=(0xfffc,0x8000) if op==16 else (0x3fffffc,0x2000000)
            delta=word&mask
            if delta&sign:delta-=2*sign
            target=sites[i+delta//4]['address']
            chunk=([(word&0xffff0000)^0x01000000|8,branch(a+4,target),branch(a+8,following)]
                   if op==16 else [branch(a,target),0x60000000])
        else:chunk=[word,branch(a+4,following)]
        if len(chunk)*4!=s['size']:raise ValueError('Random Wisp spawn slot size differs')
        result.append((a,bytes.fromhex(s['original']),struct.pack('>'+'I'*len(chunk),*chunk)))
    for hook in HOOKS:
        result.append((hook,struct.pack('>I',branch(hook,SPAWN)|1),struct.pack('>I',branch(hook,sites[0]['address'])|1)))
    if any(a<e+len(n) and e<a+len(new) for a,o,new in result for e,old,n in occupied):
        raise ValueError('Random Wisp spawn overlaps another patch')
    return result


def planned_patches():
    from .native_dol import plan
    from ..world_constants import load_data
    rows=plan()[0];first=load_data('random_wisp_spawn_sites.json')[0]['address']
    start=next(i for i,row in enumerate(rows) if row[0]==first)
    return rows[start:start+len(program(0,0))+len(HOOKS)]
