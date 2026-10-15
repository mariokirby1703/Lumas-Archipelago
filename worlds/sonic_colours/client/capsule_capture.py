"""Native successful-opening journal, independent of capsule actor lifetime."""
import struct
from .capsule_refresh import PPC
from .gecko import inspect_c2
from .memory import MemoryUnavailable

HOOK=0x800D4CF0
ORIGINAL=0xC3FC0104
CAPACITY=32
ENTRY_SIZE=32
DATA_SIZE=16+CAPACITY*ENTRY_SIZE
MAGIC=0x43415051


def payload():
    a=PPC();a.d(37,1,1,-0x60)
    a.d(36,0,1,8);a.emit(0x7C0802A6);a.d(36,0,1,12)
    a.emit(0x7C000026);a.d(36,0,1,16)
    for r in range(3,13):a.d(36,r,1,20+(r-3)*4)
    a.emit(0x48000005);base=len(a.words)*4;a.emit(0x7D8802A6)
    data_fix=len(a.words);a.d(14,12,12,0)
    a.d(32,3,28,0);a.d(15,4,0,0x8076);a.d(24,4,4,0x1534)
    a.emit(0x7C032000);a.branch('end',0x40820000)
    # The native committed-opening path follows all rejection branches and
    # unconditionally reaches the opened write. Capture BEFORE item spawning
    # can synchronously retire its ORC wrapper. Retain
    # the exact ORC instance while the wrapper and actor still exist.
    a.d(32,5,28,0x64);a.d(11,0,5,0);a.branch('end',0x41820000)
    a.d(32,3,5,4);a.emit(0x7C03E000);a.branch('end',0x40820000)
    a.d(32,6,5,8);a.d(32,7,5,12)
    a.d(11,0,6,0);a.branch('end',0x41820000)
    a.d(11,0,7,0);a.branch('end',0x41820000)
    a.d(32,3,7,0);a.d(15,4,0,0x8077);a.d(24,4,4,0x0fa0)
    a.emit(0x7C032000);a.branch('end',0x40820000)
    a.d(32,3,7,0x10);a.emit(0x7C033000);a.branch('end',0x40820000)
    a.d(32,3,7,0x1c);a.emit(0x7C032800);a.branch('end',0x40820000)
    # Resolve the active native document context; do not use a host's stale
    # mission or player pointer when opening coincides with a scene change.
    a.d(15,8,0,0x808f);a.d(32,8,8,0x336c)
    a.d(32,8,8,4);a.d(32,8,8,0x1c);a.d(32,8,8,0x34)
    a.d(11,0,8,0);a.branch('end',0x41820000)
    a.d(32,3,8,0);a.d(15,4,0,0x8075);a.d(24,4,4,0x9438)
    a.emit(0x7C032000);a.branch('end',0x40820000)
    a.d(32,9,8,0x4c)
    a.d(32,3,12,0);a.d(14,3,3,1)
    a.d(28,3,4,CAPACITY-1);a.d(7,4,4,ENTRY_SIZE)
    a.emit(0x7C8C2214);a.d(14,4,4,16)  # add r4,r12,r4
    a.d(14,10,0,0);a.d(36,10,4,0)  # invalidate a reused slot before changing payload
    # Attribute queued pickups to the exact native save container/index.
    # The low byte of the subtype word remains the raw colour (1..8).
    from .versions import VERSION
    manager=VERSION['manager_global_candidate']
    a.d(15,10,0,manager>>16);a.d(24,10,10,manager&65535)
    a.d(32,10,10,0);a.d(32,10,10,0x30);a.d(36,10,4,4)
    a.d(34,11,10,0)
    a.d(32,10,9,0);a.d(36,10,4,8)
    a.d(40,10,9,4);a.d(36,10,4,12)
    a.d(32,10,6,0);a.emit(0x554A033E);a.d(36,10,4,16)  # low 20 bits
    a.d(32,10,7,0x14);a.d(36,10,4,20)
    a.d(32,10,28,0x114);a.d(14,10,10,1)
    a.emit(21<<26|11<<21|11<<16|8<<11|23<<1)  # slwi r11,r11,8
    a.emit(31<<26|10<<21|10<<16|11<<11|444<<1)  # or r10,r10,r11
    a.d(36,10,4,24)
    a.d(32,10,28,12);a.d(36,10,4,28)
    a.emit(0x7C0004AC)  # sync: payload precedes sequence publication
    a.d(36,3,4,0);a.d(36,3,12,0)
    a.label('end')
    for r in range(3,13):a.d(32,r,1,20+(r-3)*4)
    a.d(32,0,1,16);a.emit(0x7C0FF120)
    a.d(32,0,1,12);a.emit(0x7C0803A6);a.d(32,0,1,8)
    a.d(14,1,1,0x60);a.emit(ORIGINAL);a.branch('return')
    offset=len(a.words)*4
    a.words[data_fix]=0x398C0000|(offset-base)
    for i in range(DATA_SIZE//4):a.emit(MAGIC if i==1 else 0)
    a.label('return');a.emit(0)
    return a.finish(),offset


def installed_data(memory):
    words,offset=payload()
    result=inspect_c2(memory,HOOK,ORIGINAL,{'capsule_events':words},
                      ((offset,4),(offset+8,DATA_SIZE-8)),label='capsule opening capture')
    return result['target']+offset if result['installed'] else None


def read_events(memory,after=0):
    data=installed_data(memory)
    if data is None:return None
    for _ in range(3):
        head=memory.read_u32(data)
        raw=memory.read_bytes(data+16,CAPACITY*ENTRY_SIZE)
        if memory.read_u32(data)==head:break
    else:raise MemoryUnavailable('capsule event producer changed during read')
    if head<after:after=0  # new native game lifetime
    start=max(after+1,head-CAPACITY+1)
    events=[]
    for sequence in range(start,head+1):
        words=struct.unpack_from('>8I',raw,(sequence&(CAPACITY-1))*ENTRY_SIZE)
        if words[0]!=sequence:raise MemoryUnavailable('capsule event publication incomplete')
        mission=(words[2].to_bytes(4,'big')+words[3].to_bytes(2,'big')).decode('ascii')
        events.append(dict(sequence=sequence,container=words[1],save_index=words[6]>>8,mission=mission,
                           object_id=words[4],instance=words[5],raw_wisp=words[6]&255,actor_id=words[7]))
    return head,events,max(0,head-after-CAPACITY)
