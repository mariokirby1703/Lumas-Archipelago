"""Reset current-stage score sources, never saved high-score/rank records.

PAL 8001C50C..8001C520 publishes stage+80 plus 80017358(stage+198).
80017370..80017380 sums the 21 words at +4..+54 in that accumulator.
"""
from .memory import MemoryUnavailable
from .native_read import STAGE_VTABLE


def sources(memory,snapshot):
    if snapshot.scene!='gameplay' or not snapshot.scene_verified:
        raise MemoryUnavailable('Score Reset awaits active gameplay')
    stage=next(iter(snapshot.evidence.get('native_data',{}).get('stage_objects',[])),{})
    actor=stage.get('stage')
    if actor is None or stage.get('mission')!=snapshot.actual_mission or memory.read_u32(actor)!=STAGE_VTABLE:
        raise MemoryUnavailable('Score Reset stage ownership unavailable')
    fields={actor+0x80:memory.read_bytes(actor+0x80,4),actor+0x19c:memory.read_bytes(actor+0x19c,84)}
    values=[int.from_bytes(raw[i:i+4],'big') for raw in fields.values() for i in range(0,len(raw),4)]
    if any(v>0x7fffffff for v in values):raise MemoryUnavailable('Score Reset native counters invalid')
    return actor,fields,sum(values)


def deliver(memory,snapshot,guard,journal,index,item):
    guard.check_stats(snapshot)
    actor,fields,total=sources(memory,snapshot)
    if not total:
        journal.defer(index,item,'Score Reset awaits an Act with positive score');return
    context=[snapshot.session,snapshot.stage_epoch,actor]
    journal.prepare(index,item,context,total,0)
    effect=journal.data['effects'][str(index)]
    effect.update(family='score',addresses=list(fields),completed_writes=0)
    journal.save()
    memory._score_reset_transaction=(tuple(context),{a:len(raw) for a,raw in fields.items()})
    try:
        for address,before in fields.items():
            memory.write_bytes_verified(address,bytes(len(before)),expected=before,operation='score_reset')
            effect['completed_writes']+=1;journal.save()
        if any(memory.read_bytes(a,len(raw))!=bytes(len(raw)) for a,raw in fields.items()):
            raise MemoryUnavailable('Score changed before reset confirmation')
        journal.confirm(index,verified_delivery=True)
    except MemoryUnavailable as error:
        # Any attempted transaction may have partially applied. Never replay
        # automatically and risk clearing score earned after the first reset.
        effect.update(state='uncertain',reason=str(error));journal.save()
    finally:memory._score_reset_transaction=None
