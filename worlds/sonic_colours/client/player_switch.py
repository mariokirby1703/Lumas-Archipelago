"""PAL Game Land: AP-owned Assist Change before MultiDoublePlayer transfer.

At 802F1638 command 11's predicate normally branches to the neutral return
only when not pressed. The legacy fixed patch and current predicate gate are
recognized exactly. The current gate runs before transfer messages,
effects and request 114. Other native input predicates are untouched.
"""
from .memory import MemoryUnavailable

ADDRESS=0x802F1638
ORIGINAL=0x41820244
DISABLED=0x48000244


def normalize(data,base):
    if base<=ADDRESS<base+len(data):
        offset=ADDRESS-base
        word=int.from_bytes(data[offset:offset+4],'big')
        if word not in (ORIGINAL,DISABLED):
            raise MemoryUnavailable('unknown_revision: Game Land player-switch branch')
        data=data[:offset]+ORIGINAL.to_bytes(4,'big')+data[offset+4:]
    return data


HOOK=0x802F1634
HOOK_ORIGINAL=0x2C030000


def payload():
    # The original action predicate call clobbers volatile r0/r12. At its
    # following cmpwi neither is live. Preserve LR and gate its boolean r3
    # before the original branch, hence before any transfer side effects.
    return [0x7C0802A6,0x48000005,0x7D8802A6,0x818C0018,
            0x7C636038,0x7C0803A6,HOOK_ORIGINAL,0x48000008,0,0],32


def installed_data(memory):
    from .gecko import inspect_c2
    words,offset=payload()
    info=inspect_c2(memory,HOOK,HOOK_ORIGINAL,{'assist_change':words},((offset,4),),label='Assist Change')
    return info['target']+offset if info['installed'] else None


def gecko_lines():
    words,_=payload()
    return [f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}']+[f'{words[i]:08X} {words[i+1]:08X}' for i in range(0,len(words),2)]


def configure(memory,snapshot,owned):
    data=installed_data(memory)
    if data is None:return {'status':'Assist Change hook missing; update complete Gecko profile'}
    value=int(owned['counts'].get('Assist Change',0)>0)
    before=memory.read_u32(data)
    if before!=value:memory.write_u32(data,value,expected=before,operation='assist_change')
    return {'status':'Assist Change unlocked' if value else 'Assist Change locked','allowed':bool(value)}
