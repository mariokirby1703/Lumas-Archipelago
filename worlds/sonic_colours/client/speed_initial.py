"""PAL Game Land default speed: internal 0 = Speed 1.

8026FE6C resets the singleton, bypassing the speed setter. 8026FE80's
immediate is stored at singleton+4 by 8026FE9C before any other r0 use.
Only the initial selection changes; AP getter/setter/UI caps remain in force.
"""
from .memory import MemoryUnavailable
ADDRESS=0x8026FE80
ORIGINAL=0x38000002
PATCHED=0x38000000


def normalize(data,base):
    if base<=ADDRESS<base+len(data):
        offset=ADDRESS-base
        word=int.from_bytes(data[offset:offset+4],'big')
        if word not in (ORIGINAL,PATCHED):
            raise MemoryUnavailable('unknown_revision: Game Land initial speed')
        data=data[:offset]+ORIGINAL.to_bytes(4,'big')+data[offset+4:]
    return data


def gecko_lines():
    return [f'04{ADDRESS-0x80000000:06X} {PATCHED:08X}']
