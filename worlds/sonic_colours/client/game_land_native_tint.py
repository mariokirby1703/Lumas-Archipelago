from .capsule_refresh import PPC
from .gecko import inspect_c2
from .memory import MemoryUnavailable
HOOK=0x802F0DA4
ORIGINAL=0x7F85E378
PALETTE_WORD=0x7F64DB78  # mr r4,r27 at 802F0DD4

def payload():
    a=PPC()
    # Only reached for native-uncleared Acts. r27 is the saved per-column
    # uncleared marker and becomes 1 later at 802F0E14. Original formatting
    # replaces volatile arguments immediately after this probe.
    a.d(14,3,1,12);a.d(14,4,28,7);a.mr(5,26);a.call(0x8015EE9C)
    a.d(7,3,3,-24)  # bool -> grey at r2-14C0; locked -> zero at r2-14A8
    a.d(14,27,2,-0x14a8);a.emit(0x7F7B1A14)  # add r27,r27,r3
    a.emit(ORIGINAL);a.emit(0)
    return a.finish()

def installed(memory):
    return inspect_c2(memory,HOOK,ORIGINAL,{'game_land_native_tint':payload()},label='Game Land initial tint')['installed']

def normalize(memory,data,base):
    if base<=HOOK<base+len(data):
        off=HOOK-base
        if int.from_bytes(data[off:off+4],'big')!=ORIGINAL:
            if not installed(memory):raise MemoryUnavailable('unknown_revision: Game Land initial tint')
            data=data[:off]+ORIGINAL.to_bytes(4,'big')+data[off+4:]
    return data

def gecko_lines():
    words=payload()
    return [f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}']+[f'{words[i]:08X} {words[i+1]:08X}' for i in range(0,len(words),2)]
