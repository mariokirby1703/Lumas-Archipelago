"""Native active-state permission checks, including scripted transition recovery."""
import struct
from .capsule_refresh import PPC
HOOKS={'drift':(0x80150504,0x9421FFD0,0x80769268,128,3),
       'jump':(0x80098A04,0x9421FFE0,0x8075E9B8,1,15),
       'stomp':(0x8015FED4,0x9421FFA0,0x8076A09C,64,15)}


def program(control):
    a=PPC();entries={};returns={}
    def const(r,v):a.d(15,r,0,v>>16);a.d(24,r,r,v&65535)
    def eq(l,r):a.emit(0x7C000000|l<<16|r<<11)
    for i,kind in enumerate(HOOKS):
        entries[kind]=len(a.words);a.d(14,0,0,i);a.branch('common')
    a.label('common');a.d(37,1,1,-0x50);a.d(36,0,1,0x2c)
    for r in range(9,13):a.d(36,r,1,0x30+(r-9)*4)
    a.emit(0x7C0802A6);a.d(36,0,1,0x44)
    const(12,control);a.d(32,9,12,0);a.d(11,0,9,0);a.branch('allow',0x41820000)
    a.d(32,0,1,0x2c)
    for i,kind in enumerate(HOOKS):
        a.d(11,0,0,i);a.branch('select_'+kind,0x41820000)
    for kind,(_,_,vt,mask,fallback) in HOOKS.items():
        a.label('select_'+kind);const(10,vt);a.d(14,9,0,mask);a.d(36,9,1,0x28)
        a.d(14,9,0,fallback);a.d(36,9,1,0x24);a.branch('validate')
    a.label('validate');a.d(32,9,3,0);eq(9,10);a.branch('allow',0x40820000)
    a.d(32,9,4,0);const(10,0x8075A0F8);eq(9,10);a.branch('allow',0x40820000)
    a.d(32,11,4,0x28);a.d(11,0,11,0);a.branch('allow',0x41820000)
    a.d(32,9,11,0);const(10,0x8075AEF8);eq(9,10);a.branch('allow',0x40820000)
    a.d(32,10,11,0x70);a.d(11,0,10,0);a.branch('allow',0x41820000)
    a.d(32,10,10,8);eq(10,4);a.branch('allow',0x40820000)
    # Never overwrite a queued death, scripted exit or another transition.
    a.d(32,9,4,0x20);a.d(11,0,9,-1);a.branch('stable',0x41820000)
    a.d(32,10,4,0x1c);eq(9,10);a.branch('allow',0x40820000)
    a.label('stable')
    a.d(32,10,1,0x28);a.d(11,0,10,1);a.branch('permission',0x40820000)
    a.d(32,9,11,0x8c);a.d(11,0,9,0);a.branch('allow',0x41820000)
    a.d(32,9,9,0x10);a.d(28,9,9,0x800);a.branch('permission',0x41820000)
    a.d(14,10,0,256)
    a.label('permission');a.d(32,9,12,4);a.emit(0x7D295039);a.branch('allow',0x40820000)
    # Ordinary request performs native exit/entry cleanup; no state/velocity edits.
    a.mr(3,4);a.d(32,4,1,0x24);a.call(0x80033878)
    a.d(14,3,0,1);a.branch('return')
    a.label('allow');a.d(32,0,1,0x2c)
    a.d(11,0,0,1);a.branch('allow_jump',0x41820000)
    a.d(11,0,0,2);a.branch('allow_stomp',0x41820000)
    def restore():
        for r in range(9,13):a.d(32,r,1,0x30+(r-9)*4)
        a.d(32,0,1,0x44);a.emit(0x7C0803A6);a.d(14,1,1,0x50)
    for kind in HOOKS:
        a.label('allow_'+kind);restore();a.emit(HOOKS[kind][1]);returns[len(a.words)]=HOOKS[kind][0]+4;a.emit(0)
    a.label('return');restore();a.emit(0x4E800020)
    return a.finish(),entries,returns


def patches(control,occupied):
    from ..world_constants import load_data
    from .native_dol import branch
    words,entries,returns=program(control);sites=load_data('active_movement_sites.json')
    if len(words)!=len(sites):raise ValueError('Active movement layout differs')
    result=[]
    for i,word in enumerate(words):
        site=sites[i];address=site['address'];size=site['size']
        following=sites[i+1]['address'] if i+1<len(sites) else address
        if i in returns:chunk=[branch(address,returns[i]),0x60000000]
        elif word>>26 in (16,18):
            op=word>>26;mask,sign=(0xfffc,0x8000) if op==16 else (0x3fffffc,0x2000000)
            delta=word&mask
            if delta&sign:delta-=sign*2
            target=sites[i+delta//4]['address']
            chunk=([(word&0xffff0000)^0x01000000|8,branch(address+4,target),branch(address+8,following)]
                   if op==16 else [branch(address,target),0x60000000])
        else:chunk=[word,branch(address+4,following)]
        if len(chunk)*4!=size:raise ValueError('Active movement instruction width differs')
        result.append((address,bytes.fromhex(site['original']),struct.pack('>'+'I'*len(chunk),*chunk)))
    for kind,index in entries.items():
        hook,original,*_=HOOKS[kind]
        result.append((hook,struct.pack('>I',original),struct.pack('>I',branch(hook,sites[index]['address']))))
    if any(a<e+len(n) and e<a+len(new) for a,o,new in result for e,old,n in occupied):
        raise ValueError('Active movement overlaps another patch')
    return result


def planned_patches():
    from .native_dol import plan
    from ..world_constants import load_data
    rows=plan()[0];count=len(program(0)[0])+len(HOOKS)
    first=load_data('active_movement_sites.json')[0]['address']
    start=next(i for i,row in enumerate(rows) if row[0]==first)
    return rows[start:start+count]
