"""Gate the native Quick Step predicate before flags and forced state entry."""
from .gecko import inspect_c2
from .memory import MemoryUnavailable

HOOK=0x80091C60
ORIGINAL=0x2C030000
ITEM='Quick Step'


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
        info=inspect_c2(memory,HOOK,ORIGINAL,{'quick_step':words},((offset,4),),label='Quick Step')
    except MemoryUnavailable:
        words,offset=payload(True)
        info=inspect_c2(memory,HOOK,ORIGINAL,{'quick_step':words},((offset,4),),label='Quick Step')
    if not info['installed']:return None
    address=info['target']+offset
    if memory.read_u32(address)>1:raise MemoryUnavailable('unknown_revision: Quick Step permission')
    return address


def configure(memory,snapshot,owned,enabled=True):
    address=installed_data(memory)
    if address is None:return {'status':'Update Gecko profile for Quick Step','installed':False}
    level=min(2,max(0,owned['counts'].get(ITEM,0)))
    value=int(not enabled or level>=1)
    before=memory.read_u32(address)
    if before!=value:memory.write_u32(address,value,expected=before,operation='quick_step')
    return {'status':'Quick Step unlocked' if value else 'Quick Step locked',
            'installed':True,'level':level,'allowed':bool(value),'live_verified':False}


def normalize(memory,data,base):
    if base<=HOOK<base+len(data):
        offset=HOOK-base
        if int.from_bytes(data[offset:offset+4],'big')!=ORIGINAL:
            if installed_data(memory) is None:raise MemoryUnavailable('unknown_revision: Quick Step hook')
            data=data[:offset]+ORIGINAL.to_bytes(4,'big')+data[offset+4:]
    return data


def gecko_lines():
    words,_=payload()
    return [f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}']+[
        f'{words[i]:08X} {words[i+1]:08X}' for i in range(0,len(words),2)]
