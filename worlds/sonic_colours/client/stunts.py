"""PAL TrickJump stunt animation/reward gate, leaving launch/landing intact.

State 46 calls 80148454 to perform a stunt, rather than requesting a new
movement state. Without AP permission it returns false before any side effects.
"""
from .gecko import inspect_c2
from .memory import MemoryUnavailable
HOOK=0x80148454
ORIGINAL=0x9421FF60
ITEM='Progressive Stunts'
LABELS=('Good','Great','Awesome','Outstanding','Amazing')


def payload():
    # Function-call ABI: r0/r12/CR are volatile. Preserve caller LR before
    # early return; authorized entry executes the original stack prologue.
    # Native 80148480 compares TrickJump+22C (performed count) against
    # +230 (ramp's own limit). Apply the AP limit before that native logic.
    return [0x7C0802A6,0x48000005,0x7D8802A6,0x818C0028,
            0x7C0803A6,0x8003022C,0x7C006040,0x4180000C,
            0x38600000,0x4E800020,ORIGINAL,0x48000008,
            0,0],48



def installed_data(memory):
    words,offset=payload()
    try:
        info=inspect_c2(memory,HOOK,ORIGINAL,{'progressive_stunts':words},((offset,4),),label='Progressive Stunts')
        memory.stunts_legacy=False
    except MemoryUnavailable:
        old=[0x7C0802A6,0x48000005,0x7D8802A6,0x818C001C,0x7C636039,0x7C0803A6,0x4D820020,ORIGINAL,0x48000008,0,0x60000000,0]
        info=inspect_c2(memory,HOOK,ORIGINAL,{'stunts_legacy':old},((36,4),),label='previous Stunts')
        offset=36;memory.stunts_legacy=True
    return info['target']+offset if info['installed'] else None


def normalize(memory,data,base):
    if base<=HOOK<base+len(data):
        offset=HOOK-base
        word=int.from_bytes(data[offset:offset+4],'big')
        if word!=ORIGINAL:
            if installed_data(memory) is None:raise MemoryUnavailable('unknown_revision: Stunts hook')
            data=data[:offset]+ORIGINAL.to_bytes(4,'big')+data[offset+4:]
    return data


def gecko_lines():
    words,_=payload()
    return [f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}']+[f'{words[i]:08X} {words[i+1]:08X}' for i in range(0,len(words),2)]


def configure(memory,snapshot,owned,slot):
    data=installed_data(memory)
    if data is None:return {'status':'Stunts hook missing; update complete Gecko profile'}
    if getattr(memory,'stunts_legacy',False):return {'status':'Update complete Gecko profile for Progressive Stunts'}
    value=5 if not slot['options'].get('movement_unlocks') else min(5,max(0,owned['counts'].get(ITEM,0)))
    allowed=value>0
    before=memory.read_u32(data)
    if before!=value:memory.write_u32(data,value,expected=before,operation='stunts')
    return {'status':'Stunts unlocked' if allowed else 'Stunts locked; ramp launch preserved','allowed':bool(allowed),'level':value,'maximum_quality':LABELS[value-1] if value else None,'live_verified':False}
