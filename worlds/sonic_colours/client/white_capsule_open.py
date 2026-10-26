"""Deny ordinary White capsule opening before any capture/reward side effects.

Default-deny White until authenticated capsule permissions are published.
Random/multi capsules retain their independent policy. Native opening failure
uses r3 != 0 at 800D4CE8, before the committed pickup journal and rewards.
"""
import struct
from .capsule_refresh import PPC
HOOK=0x800D4CE8
ORIGINAL=0x2C030000


def program(capsule_control):
    a=PPC()
    a.d(11,0,3,0);a.branch('done',0x40820000)
    a.d(34,0,28,0x148);a.d(11,0,0,0);a.branch('done',0x40820000)
    a.d(34,0,28,0x14a);a.d(11,0,0,0);a.branch('done',0x40820000)
    a.d(32,0,28,0x114);a.d(11,0,0,-1);a.branch('done',0x40820000)
    a.d(15,12,0,capsule_control>>16);a.d(24,12,12,capsule_control&65535)
    a.d(32,5,12,0);a.d(11,0,5,0);a.branch('deny',0x41820000)
    a.d(34,0,5,0);a.d(32,6,12,4);a.emit(0x7C003000);a.branch('deny',0x40820000)
    a.d(10,0,6,3);a.branch('deny',0x41810000)
    a.d(32,0,12,8);a.d(28,0,0,1);a.branch('done',0x40820000)
    a.label('deny');a.d(14,3,0,1)
    a.label('done');a.emit(ORIGINAL);a.emit(0)
    return a.finish()


def patches(capsule_control,occupied):
    from ..world_constants import load_data
    from .native_dol import branch
    sites=load_data('white_capsule_open_sites.json');words=program(capsule_control)
    if len(words)!=len(sites):raise ValueError('White capsule opening layout differs')
    result=[]
    for i,word in enumerate(words):
        s=sites[i];a=s['address'];following=sites[i+1]['address'] if i+1<len(sites) else HOOK+4
        if i==len(words)-1:chunk=[branch(a,HOOK+4),0x60000000]
        elif word>>26 in (16,18):
            op=word>>26;mask,sign=(0xfffc,0x8000) if op==16 else (0x3fffffc,0x2000000)
            delta=word&mask
            if delta&sign:delta-=2*sign
            target=sites[i+delta//4]['address']
            chunk=([(word&0xffff0000)^0x01000000|8,branch(a+4,target),branch(a+8,following)]
                   if op==16 else [branch(a,target),0x60000000])
        else:chunk=[word,branch(a+4,following)]
        if len(chunk)*4!=s['size']:raise ValueError('White capsule opening slot size differs')
        result.append((a,bytes.fromhex(s['original']),struct.pack('>'+'I'*len(chunk),*chunk)))
    result.append((HOOK,struct.pack('>I',ORIGINAL),struct.pack('>I',branch(HOOK,sites[0]['address']))))
    if any(a<e+len(n) and e<a+len(new) for a,o,new in result for e,old,n in occupied):
        raise ValueError('White capsule opening overlaps another patch')
    return result


def planned_patches():
    from .native_dol import plan
    from ..world_constants import load_data
    rows=plan()[0];first=load_data('white_capsule_open_sites.json')[0]['address']
    start=next(i for i,row in enumerate(rows) if row[0]==first)
    return rows[start:start+len(program(0))+1]
