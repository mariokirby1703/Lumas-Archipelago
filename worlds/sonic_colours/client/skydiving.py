"""PAL Diving callback: native Fall and cleanup without Skydiving.

The callback receives state r3, owned machine r4. At this entry no stack
frame exists. A locked update tail-calls the original request setter with
Fall (15); dispatch performs native exit/entry. No state or velocity edits.
"""
from .capsule_refresh import PPC
from .gecko import inspect_c2
from .memory import MemoryUnavailable

HOOK, ORIGINAL = 0x8025C014, 0x9421FFF0
FALL = 15


def payload():
    a = PPC()
    for word in (0x7C0802A6,0x48000005,0x7D8802A6):a.emit(word)
    fix = len(a.words); a.d(32,12,12,0)
    a.emit(0x7C0803A6)
    a.d(11,0,12,1); a.branch('vanilla',0x40820000)
    a.mr(3,4); a.d(14,4,0,FALL)
    a.d(15,12,0,0x8003); a.d(24,12,12,0x3878)
    a.emit(0x7D8903A6);a.emit(0x4E800420)
    a.label('vanilla'); a.emit(ORIGINAL); a.branch('return')
    offset = len(a.words)*4; a.words[fix] |= (offset-8)&0xffff
    a.emit(0)  # inert until authenticated client publishes lock=1
    a.label('return')
    if len(a.words)%2==0:a.emit(0x60000000)
    a.emit(0)
    return a.finish(),offset


def installed_data(memory):
    words,offset=payload()
    info=inspect_c2(memory,HOOK,ORIGINAL,{'skydiving':words},((offset,4),),'Skydiving')
    if not info['installed']:return None
    address=info['target']+offset
    if memory.read_u32(address)>1:raise MemoryUnavailable('unknown_revision: Skydiving permission')
    return address


def configure(memory,snapshot,owned):
    address=installed_data(memory)
    if address is None:return {'status':'Update Gecko profile for Skydiving','installed':False}
    locked=int(owned['counts']['Progressive Skydiving']==0)
    before=memory.read_u32(address)
    if before!=locked:memory.write_u32(address,locked,expected=before,operation='skydiving')
    return {'status':'Skydiving locked: native Fall on each Diving update' if locked else 'Skydiving unlocked',
            'installed':True,'locked':bool(locked),'visual_verified':False}


def normalize(memory,data,start):
    if start<=HOOK<start+len(data):
        off=HOOK-start
        if int.from_bytes(data[off:off+4],'big')!=ORIGINAL and installed_data(memory) is not None:
            data=data[:off]+ORIGINAL.to_bytes(4,'big')+data[off+4:]
    return data


def gecko_lines():
    words,_=payload()
    return [f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}']+[
        f'{words[i]:08X} {words[i+1]:08X}' for i in range(0,len(words),2)]
