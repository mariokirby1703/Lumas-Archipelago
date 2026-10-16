"""PAL oxygen entry and bubble-reset policy, on the game thread.

Only a data mailbox is host-writable. Both displaced instructions are checked
against the original DOL. Legacy Gecko clients retain the guarded host fallback.
"""
import struct
from .capsule_refresh import PPC
from .memory import MemoryUnavailable
MAGIC=0x41504F32
SIZE=32
UPDATE,RESET=0x801F0BAC,0x801F11E8
ORIGINAL_UPDATE,ORIGINAL_RESET=0xC03D0020,0xD0030020


def payload(start,control):
    a=PPC()
    def const(r,v):a.d(15,r,0,v>>16);a.d(24,r,r,v&65535)
    def eq(l,r):a.emit(0x7C000000|l<<16|r<<11)
    def reject():a.branch('vanilla',0x40820000)
    def prologue(mode):
        a.d(37,1,1,-0x60);a.d(36,0,1,12)
        for r in range(3,9):a.d(36,r,1,16+4*(r-3))
        a.emit(0x7C000026);a.d(36,0,1,40)
        a.d(54,0,1,48);a.d(54,1,1,56)
        a.d(14,8,0,mode)
    prologue(0);a.mr(3,29);a.mr(4,30);a.branch('common')
    reset=start+len(a.words)*4
    prologue(1)
    a.label('common');const(5,control)
    a.d(32,6,5,4);a.d(11,0,6,1);reject()
    a.d(32,6,3,0);const(7,0x807710FC);eq(6,7);reject()
    a.d(32,6,4,0);const(7,0x8075A0F8);eq(6,7);reject()
    a.d(32,6,4,0x28);a.d(11,0,6,0);a.branch('vanilla',0x41820000)
    a.d(32,7,6,0);const(0,0x8075AEF8);eq(7,0);reject()
    a.d(32,7,6,0x70);a.d(11,0,7,0);a.branch('vanilla',0x41820000)
    a.d(32,7,7,8);eq(4,7);reject()
    # A map-preloaded policy cannot follow the player to another save slot.
    from .versions import VERSION
    const(7,VERSION['manager_global_candidate']);a.d(32,7,7,0)
    a.d(11,0,7,0);a.branch('vanilla',0x41820000)
    a.d(32,7,7,0x30);a.d(32,0,5,8);eq(7,0);reject()
    a.d(34,7,7,0);a.d(32,0,5,12);eq(7,0);reject()
    a.d(48,0,5,16) # native elapsed floor: 30 - granted seconds
    a.d(11,0,8,1);a.branch('reset',0x41820000)
    a.d(32,7,5,20);eq(3,7);a.branch('fresh',0x40820000)
    a.d(32,7,6,12);a.d(32,0,5,28);eq(7,0);a.branch('fresh',0x40820000)
    # Water re-entry can reuse the same plugin and actor serial while the
    # native timer is reset outside the bubble-reset path. Positive floors
    # (0..20 seconds of granted air) must be reapplied immediately, not after
    # the host eventually samples that reset. IEEE positive floats retain
    # integer ordering; do not use it for negative floors (40/60 seconds).
    a.d(32,7,5,24);a.d(11,0,7,0);a.branch('adjust',0x40810000)
    a.d(32,0,3,0x20);eq(0,7);a.branch('fresh',0x41800000)
    a.label('adjust')
    # Preserve remaining air when the received progressive level changes.
    a.d(48,1,3,0x20);a.d(48,0,5,24)
    a.emit(0xEC210028) # fsubs f1,f1,f0
    a.d(48,0,5,16);a.emit(0xEC21002A) # fadds f1,f1,f0
    a.d(52,1,3,0x20);a.branch('remember')
    a.label('fresh')
    # On first update, retain time already advanced by the native frame.
    a.d(48,1,3,0x20);a.emit(0xEC21002A);a.d(52,1,3,0x20);a.branch('remember')
    a.label('reset');a.d(52,0,3,0x20)
    a.label('remember');a.d(36,3,5,20);a.d(52,0,5,24)
    a.d(32,7,6,12);a.d(36,7,5,28)
    a.branch('finish')
    a.label('vanilla')
    a.d(11,0,8,1);a.branch('finish',0x40820000)
    # Reset's original store must still execute when the policy is disabled.
    a.d(50,0,1,48);a.d(52,0,3,0x20)
    a.label('finish');a.d(11,0,8,1);a.branch('reset_return',0x41820000)
    def restore():
        a.d(50,0,1,48);a.d(50,1,1,56)
        a.d(32,0,1,40);a.emit(0x7C0FF120)
        for r in range(3,9):a.d(32,r,1,16+4*(r-3))
        a.d(32,0,1,12);a.d(14,1,1,0x60)
    restore();a.emit(ORIGINAL_UPDATE)
    update_return=len(a.words);a.emit(0)
    a.label('reset_return');restore();reset_return=len(a.words);a.emit(0)
    words=a.finish()
    from .native_dol import branch
    words[update_return]=branch(start+update_return*4,UPDATE+4)
    words[reset_return]=branch(start+reset_return*4,RESET+4)
    return struct.pack('>'+'I'*len(words),*words),reset


def address(memory):
    from .native_dol import plan,ARENA
    from .native_events import SIZE as EVENT_SIZE
    if not getattr(memory,"native_patch",None):return None
    base=ARENA+len(plan()[1])-EVENT_SIZE-SIZE
    if memory.read_u32(base)!=MAGIC:raise MemoryUnavailable('oxygen mailbox signature changed')
    size=len(payload(0x80002000,base)[0]);start=base-size
    expected,_=payload(start,base)
    if memory.read_bytes(start,size)!=expected:raise MemoryUnavailable('oxygen executable changed')
    return base


def context(memory,snapshot,guard):
    if snapshot.scene not in ('gameplay','world_map','global_map','game_land_select','results','dying','respawning') or not snapshot.scene_verified:
        raise MemoryUnavailable('Oxygen policy awaits attributed gameplay or map')
    if not guard.can_record_pickups(snapshot):guard.check(snapshot)
    chain=memory.resolve_selected_slot(allow_working=True)
    observed=snapshot.evidence.get('chain') or snapshot.evidence.get('save_chain_trace',{}).get('chain')
    if observed and tuple(chain[:3])!=tuple(observed[:3]):
        raise MemoryUnavailable('Oxygen profile changed after snapshot')
    return snapshot.session,chain[1],chain[2]


def configure(memory,snapshot,guard,owned):
    from .water_native import duration
    base=address(memory)
    if base is None:return None
    seconds=duration(owned['counts'])
    try:token=context(memory,snapshot,guard)
    except MemoryUnavailable:
        fields={4:bytes(4)};token=None
    else:fields={4:bytes(4),8:struct.pack('>II',token[1],token[2]),16:struct.pack('>f',30.05 if seconds==0 else 30-seconds)}
    status={'status':'game-thread oxygen entry/reset policy armed' if token else 'oxygen policy disabled: unauthenticated scene',
            'air_seconds':seconds,'installed':True,'live_verified':False}
    if token and memory.read_bytes(base+4,16)==struct.pack('>III',1,token[1],token[2])+fields[16]:return status
    memory._oxygen_transaction=(base,token,fields)
    try:
        for off,raw in fields.items():
            old=memory.read_bytes(base+off,len(raw))
            if old!=raw:memory.write_bytes_verified(base+off,raw,expected=old,operation='oxygen_controls')
        if token:
            fields[4]=struct.pack('>I',1)
            memory.write_bytes_verified(base+4,fields[4],expected=bytes(4),operation='oxygen_controls')
    finally:memory._oxygen_transaction=None
    return status
