"""Capture the native 1-Up contact success before actor removal."""
import struct
from .capsule_refresh import PPC
from .gecko import inspect_c2
from .memory import MemoryUnavailable
from .progression_hook import identity_tag
HOOK=0x8021227C
ORIGINAL=0x801E00BC
VTABLE=0x807727C8

def payload():
    a=PPC();a.emit(0x48000005);base=len(a.words)*4;a.emit(0x7D8802A6)
    def equal(ra,rb):
        a.emit(0x7C000000|ra<<16|rb<<11);a.branch('end',0x40820000)
    a.d(32,3,12,0);equal(3,30)
    a.d(32,3,30,12);a.d(32,4,12,4);equal(3,4)
    # Exact actor pointer plus native actor serial binds the host-validated
    # ORC record, even if the allocator reuses this address in a later stage.
    a.d(32,3,12,12);a.d(32,4,12,16);a.emit(0x7C632378);a.d(36,3,12,12)
    a.label('end');a.emit(ORIGINAL);a.branch('return');offset=len(a.words)*4
    for i,w in enumerate(a.words):
        if w>>26 in (32,36) and (w>>16)&31==12:a.words[i]=(w&0xffff0000)|(((w&0xffff)+offset-base)&0xffff)
    for _ in range(6):a.emit(0)
    a.label('return')
    if len(a.words)%2==0:a.emit(0x60000000)
    a.emit(0)
    return a.finish(),offset

def installed_data(memory):
    words,offset=payload();r=inspect_c2(memory,HOOK,ORIGINAL,{'one_up':words},((offset,24),),'1-Up capture')
    return r['target']+offset if r['installed'] else None

def normalize(memory,data,base):
    if base<=HOOK<base+len(data):
        off=HOOK-base
        if int.from_bytes(data[off:off+4],'big')!=ORIGINAL:
            if installed_data(memory) is None:raise MemoryUnavailable('unknown_revision: 1-Up capture')
            data=data[:off]+ORIGINAL.to_bytes(4,'big')+data[off+4:]
    return data

def gecko_lines():
    words,_=payload()
    return [f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}']+[f'{words[i]:08X} {words[i+1]:08X}' for i in range(0,len(words),2)]

def configure(memory,snapshot,guard,slot):
    data=installed_data(memory)
    if data is None:return {'installed':False,'status':'Update Gecko profile for 1-Up Sanity'}
    journal=guard.journal;tag=identity_tag(journal.identity)
    old=struct.unpack('>6I',memory.read_bytes(data,24))
    from ..oneups import ONEUPS
    if old[5]==tag and old[3]:
        if not guard.can_record_pickups(snapshot):guard.check(snapshot)
        rows=[r for i,r in enumerate(ONEUPS.values()) if old[3]&(1<<i) and r['location_name'] in slot['locations']]
        checks={r['code'] for r in rows}-set(journal.data['pickup_checks'])
        if checks:journal.record_pickups([{'kind':'one_up','mission':r['mission_id'],'instance_key':r['key'],'provenance':'PAL_8021227C_native_contact_success'} for r in rows if r['code'] in checks],{},checks)
    row=None
    if slot['options'].get('one_up_sanity') and snapshot.scene=='gameplay' and snapshot.scene_verified and guard.can_record_pickups(snapshot):
        from .native_read import read_oneups,read_actors
        stage=next(iter(snapshot.evidence.get('native_data',{}).get('stage_objects',[])),{})
        if stage.get('mission')==snapshot.actual_mission:
            rows=read_oneups(memory,stage['stage'],snapshot.actual_mission,read_actors(memory,stage['stage']))
            row=rows[0] if len(rows)==1 else None
    mask=old[3] if old[5]==tag else 0
    index=next((i for i,r in enumerate(ONEUPS.values()) if row and r['key']==row['key']),None)
    values=(row['actor'] if row else 0,row['actor_id'] if row else 0,row['record'] if row else 0,mask,1<<index if index is not None else 0,tag)
    if old!=values:
        memory._oneup_allowed=data
        try:
            if old[0]:memory.write_u32(data,0,expected=old[0],operation='one_up_controls')
            for i in (1,2,3,4,5):
                before=memory.read_u32(data+i*4)
                if before!=values[i]:memory.write_u32(data+i*4,values[i],expected=before,operation='one_up_controls')
            if values[0]:memory.write_u32(data,values[0],expected=0,operation='one_up_controls')
        finally:memory._oneup_allowed=None
    return {'installed':True,'armed':bool(row),'pickup_latch':mask,'mission':snapshot.actual_mission,'status':'native 1-Up capture active','live_hook_verified':False}
