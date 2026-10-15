"""PAL manual Drill turbo predicate; native movement/effects stay authoritative.

80104CB8 calls the native held-action predicate, then updates Drill+60 and
reconciles its effect through 80104DDC. Mask only that predicate, preserving
the game's forced acceleration timers and normal drilling.
"""
from .gecko import inspect_c2
from .memory import MemoryUnavailable

HOOK=0x80104D08
ORIGINAL=0x2C030000
ITEM='Progressive Yellow Drill Wisp'


def payload(preserve_lr=False):
    # r0/r12 are caller-clobbered by the preceding native input query.
    # Displaced cmpwi supplies CR0; the enclosing native epilogue restores LR.
    if preserve_lr:
        return [0x7C0802A6,0x48000005,0x7D8802A6,0x818C0018,
                0x7C636038,0x7C0803A6,ORIGINAL,0x48000008,0,0],32
    # All enclosing native routines restore their saved LR in the epilogue.
    return [0x48000005,0x7D8802A6,0x818C0014,0x7C636038,
            ORIGINAL,0x48000008,0,0],24


def installed_data(memory):
    words,offset=payload()
    try:
        info=inspect_c2(memory,HOOK,ORIGINAL,{'drill_turbo':words},((offset,4),),label='Drill turbo')
    except MemoryUnavailable:
        words,offset=payload(True)
        info=inspect_c2(memory,HOOK,ORIGINAL,{'drill_turbo':words},((offset,4),),label='Drill turbo')
    if not info['installed']:return None
    address=info['target']+offset
    if memory.read_u32(address)>1:raise MemoryUnavailable('unknown_revision: Drill turbo permission')
    return address


def configure(memory,snapshot,owned):
    address=installed_data(memory)
    if address is None:return {'status':'Update Gecko profile for Drill turbo','installed':False}
    from ..wisps import wisp_level
    level=wisp_level(owned['counts'],'Yellow Drill')
    value=int(level>=2)
    before=memory.read_u32(address)
    if before!=value:memory.write_u32(address,value,expected=before,operation='drill_turbo')
    return {'status':'Drill turbo unlocked' if value else 'Drill turbo locked',
            'installed':True,'level':level,'allowed':bool(value),'live_verified':False}


def normalize(memory,data,base):
    if base<=HOOK<base+len(data):
        offset=HOOK-base
        if int.from_bytes(data[offset:offset+4],'big')!=ORIGINAL:
            if installed_data(memory) is None:raise MemoryUnavailable('unknown_revision: Drill turbo hook')
            data=data[:offset]+ORIGINAL.to_bytes(4,'big')+data[offset+4:]
    return data


def gecko_lines():
    words,_=payload()
    return [f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}']+[
        f'{words[i]:08X} {words[i+1]:08X}' for i in range(0,len(words),2)]
