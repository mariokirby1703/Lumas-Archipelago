"""Host data-only publication to the initialized PAL game-thread mailbox."""
import struct
from . import native_events as n
from .memory import MemoryUnavailable


def owner(snapshot):
    row=next(iter(snapshot.evidence.get('native_data',{}).get('stage_objects',[])),{})
    player=row.get('player',{})
    if snapshot.scene!='gameplay' or not snapshot.scene_verified or snapshot.death_state!='alive':
        raise MemoryUnavailable('Native request awaits living gameplay')
    if not row.get('stage') or not player.get('actor') or not row.get('player_actor_id'):
        raise MemoryUnavailable('Native request owner unavailable')
    return row,player


def write(memory,snapshot,guard,fields,disable=False,cancel=False):
    base=n.address(memory)
    if not disable and not cancel:
        guard.check_stats(snapshot)
        row,player=owner(snapshot)
        context=(snapshot.session,snapshot.stage_epoch,row['stage'],player['actor'],row['player_actor_id'])
    else:context=None
    allowed={base+off:len(raw) for off,raw in fields.items()}
    memory._event_transaction={'allowed':allowed,'context':context,'disable':disable,'cancel':cancel,'values':fields}
    try:
        for off,raw in fields.items():
            address=base+off;before=memory.read_bytes(address,len(raw))
            if before!=raw:memory.write_bytes_verified(address,raw,expected=before,operation='native_event_controls')
    finally:memory._event_transaction=None


def configure(runtime,memory):
    snap=runtime.snapshot;guard=runtime.guard
    base=n.address(memory)
    try:
        guard.check_stats(snap);row,player=owner(snap)
    except MemoryUnavailable:
        write(memory,snap,guard,{n.ENABLE:bytes(4)},disable=True)
        return n.status(memory)
    key=(snap.session,snap.stage_epoch,row['stage'],player['actor'],row['player_actor_id'])
    if getattr(runtime,'_event_owner',None)!=key:
        write(memory,snap,guard,{n.ENABLE:bytes(4)},disable=True)
        # A client restart/session change must never execute an old request.
        fields={n.STAGE:struct.pack('>III',row['stage'],player['actor'],row['player_actor_id']),
                n.REQUEST:memory.read_bytes(base+n.ACK,4),
                n.INPUT:memory.read_bytes(player['actor']+0x88,4)}
        if getattr(runtime,'_event_owner',None) is None:
            request=memory.read_u32(base+n.TRAP_REQUEST)
            retained=any(e.get('family')=='dead_weight' and e.get('native_request')==request
                         and e.get('state') in ('confirmed','verifying')
                         for e in runtime.journal.data['effects'].values())
            if not retained:fields[n.REMAINING]=bytes(4)
        write(memory,snap,guard,fields)
        write(memory,snap,guard,{n.ENABLE:struct.pack('>I',1)})
        runtime._event_owner=key
    elif memory.read_u32(base+n.ENABLE)!=1:
        write(memory,snap,guard,{n.ENABLE:struct.pack('>I',1)})
    return n.status(memory)


def safe_kill(snapshot):
    try:row,player=owner(snapshot)
    except MemoryUnavailable:return False
    current=player.get('movement',{}).get('current_id',-1)
    return current in range(64) and current not in (24,25,26) and player.get('held_wisp',-1)==-1


def request_kill(memory,snapshot,guard):
    if not safe_kill(snapshot):raise MemoryUnavailable('DeathLink awaits a safe normal-Sonic state')
    state=n.status(memory)
    request=(state['remote_ack']+1)&0xffffffff or 1
    write(memory,snapshot,guard,{n.REQUEST:struct.pack('>I',request)})
    return request


def cancel_kill(memory,snapshot,guard,request=None):
    base=n.address(memory)
    # Disarm before cancelling. A later completed frame is the guest-side
    # barrier: alive samples or a host write/readback alone are insufficient.
    write(memory,snapshot,guard,{n.ENABLE:bytes(4)},disable=True)
    ack=memory.read_u32(base+n.ACK)
    write(memory,snapshot,guard,{n.REQUEST:memory.read_bytes(base+n.ACK,4)},cancel=True)
    if request is None or ack==request:
        return False  # consumed request may still be transitioning to death
    key=(base,snapshot.session,request,ack)
    previous=getattr(memory,'_kill_cancel_fence',None)
    counter=memory.read_u32(base+n.FRAME_FENCE)
    memory._kill_cancel_fence=(key,counter)
    return bool(previous and previous[0]==key and previous[1]!=counter
                and memory.read_u32(base+n.REQUEST)==ack
                and memory.read_u32(base+n.ACK)==ack)
