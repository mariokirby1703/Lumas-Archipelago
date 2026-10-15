"""Original PAL CPluginStateInWater ownership and oxygen clock reads.

801066E8 traverses the request machine's +34 plugin collection by name.
801F0BAC..0BB8 increments water-plugin +20; 801F125C computes remaining
air, 801F11E8 resets it, and 801F0BB0/0C10 use 30/13 second thresholds.
Writes are restricted to the owned elapsed clock through WritePolicy.
"""
import math
import struct
from .memory import MemoryUnavailable

VTABLE=0x807710FC
NAME=0x8071F010
TOTAL_ADDRESS=0x808F8610
WARNING_ADDRESS=0x808F8614
WARNING_ELAPSED=30.05  # vanilla 30-second limit minus 5 seconds of remaining air
# Compare against the actual native float32. Comparing with Python's 17.05
# would repeatedly classify the rounded value as below the requested floor.


def read(memory, player):
    from .movement_gate import observed
    machine=observed(memory,player)['request_machine']
    collection=memory.read_ptr_checked(machine+0x34,0x10)
    sentinel=collection+8
    node=memory.read_ptr_checked(collection+0xc,12)
    seen=set();matches=[]
    while node!=sentinel:
        if node in seen or len(seen)>=128:
            raise MemoryUnavailable('water plugin collection cycle/limit')
        seen.add(node)
        plugin=memory.read_ptr_checked(node+8,0x38)
        if memory.read_u32(plugin+8)==NAME:
            if memory.read_u32(plugin)!=VTABLE:
                raise MemoryUnavailable('water plugin vtable changed')
            matches.append(plugin)
        node=memory.read_ptr_checked(node+4,12)
    if len(matches)!=1:
        raise MemoryUnavailable('unique owned Water plugin unavailable')
    plugin=matches[0]
    total,warning=memory.read_f32(TOTAL_ADDRESS),memory.read_f32(WARNING_ADDRESS)
    elapsed=memory.read_f32(plugin+0x20)
    if total!=30.0 or warning!=13.0 or not math.isfinite(elapsed) or not -30<=elapsed<=120:
        raise MemoryUnavailable('native oxygen constants/elapsed value invalid')
    if (observed(memory,player)['request_machine']!=machine
            or memory.read_u32(machine+0x34)!=collection
            or memory.read_u32(plugin)!=VTABLE or memory.read_u32(plugin+8)!=NAME):
        raise MemoryUnavailable('water plugin owner changed')
    return {'plugin':plugin,'elapsed_address':plugin+0x20,'elapsed_seconds':elapsed,
            'remaining_seconds':max(0.0,total-elapsed),'vanilla_seconds':total,
            'warning_seconds':warning,'native_warning_phase':total-elapsed<=warning,
            'ownership':'original named plugin list of actor-owned request machine',
            'write_verified':False}


def target(memory, snapshot, guard):
    if not guard.can_record_pickups(snapshot):
        raise MemoryUnavailable('Breath requires authenticated playthrough')
    if snapshot.scene!='gameplay' or snapshot.death_state!='alive' or snapshot.stable_polls<1:
        raise MemoryUnavailable('Breath requires stable living gameplay')
    stage=next(iter(snapshot.evidence.get('native_data',{}).get('stage_objects',[])),{})
    player=stage.get('player',{}).get('actor')
    if player is None:raise MemoryUnavailable('Breath player unavailable')
    stats=memory.read_ptr_checked(player+0x8c,0x14)
    if memory.read_u32(stats)!=0x8075E088 or not memory.read_u32(stats+0x10)&0x800:
        raise MemoryUnavailable('Breath deferred: player not underwater')
    clock=read(memory,player)
    return player,clock


DURATIONS=(0,5,10,20,40,60)


def duration(counts):
    # Existing seeds retain the old Breath item's vanilla 30 seconds.
    if counts.get('Breath',0)>0:return 30
    return DURATIONS[min(5,max(0,counts.get('Progressive Breathing',0)))]


def allocation_key(memory,snapshot,player,plugin):
    """Heap addresses are not a Dolphin lifetime or stage identity."""
    backend=memory.backend
    if hasattr(backend,'instance_info'):
        info=backend.instance_info()
        backend.assert_instance(info)
        candidates=info.get('process_candidates',[])
        pid=info.get('selected_pid') or (candidates[0]['pid'] if len(candidates)==1 else None)
        if pid is None:
            raise MemoryUnavailable('Breath process identity unavailable')
        instance=f'pid-{pid}'
    else:
        instance=f'session-{snapshot.session}'
    stage=next(iter(snapshot.evidence.get('native_data',{}).get('stage_objects',[])),{})
    return f'{instance}:{snapshot.actual_mission if hasattr(snapshot,"actual_mission") else ""}:{stage.get("stage",0):08x}:{stage.get("death_count",0)}:{player:08x}:{plugin:08x}'


def configure(memory,snapshot,guard,owned,journal=None):
    seconds=duration(owned['counts'])
    records=getattr(memory,'_oxygen_records',None)
    if records is None:records=dict(journal.data.get('oxygen_live',{})) if journal else {}
    memory._oxygen_records=records
    try:player,clock=target(memory,snapshot,guard)
    except MemoryUnavailable as error:
        if 'not underwater' in str(error) and records:
            records.clear()
            if journal:journal.data['oxygen_live']={};journal.save()
        return {'status':str(error),'write_verified':False,'air_seconds':seconds}
    key=allocation_key(memory,snapshot,player,clock['plugin'])
    elapsed=clock['elapsed_seconds'];previous=records.get(key)
    # A bubble may reset to zero and advance several frames before the next
    # host sample. Do not require witnessing the short near-zero window.
    reset=(previous is not None and (
        elapsed < previous['elapsed']-0.001
        or abs(elapsed)<0.1 and abs(elapsed-previous['elapsed'])>0.5
        or seconds<30 and elapsed < 30-seconds-0.001))
    fresh=previous is None or reset
    if fresh:
        desired=30.05 if seconds==0 else 30-seconds+elapsed
    elif previous['seconds']!=seconds:
        desired=elapsed+previous['seconds']-seconds
    else:
        previous['elapsed']=elapsed
        if journal and abs(elapsed-previous.get('checkpoint',elapsed))>=1:
            previous['checkpoint']=elapsed;journal.data['oxygen_live']=records;journal.save()
        return {**clock,'status':'native oxygen lifecycle running; clock untouched','air_seconds':seconds}
    desired=max(-30,min(30.05,desired))
    before=struct.pack('>f',elapsed);after=struct.pack('>f',desired)
    prior_records=dict(records)
    records.clear();records[key]={'seconds':seconds,'elapsed':desired,'checkpoint':desired}
    if journal:journal.data['oxygen_live']=records;journal.save()
    memory._breath_transaction=(player,clock['plugin'],before,after,seconds)
    try:
        if before!=after:
            memory.write_bytes_verified(clock['elapsed_address'],after,expected=before,operation='breath_timer')
    except MemoryUnavailable as error:
        if str(error).startswith('WRITE_BLOCKED'):
            records.clear();records.update(prior_records)
            if journal:journal.data['oxygen_live']=records;journal.save()
        raise
    finally:memory._breath_transaction=None
    return {**clock,'status':'progressive oxygen duration applied; native warning/death handles playback',
            'elapsed_seconds':desired,'air_seconds':seconds,'write_verified':True}
