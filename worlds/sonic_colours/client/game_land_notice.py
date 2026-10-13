"""PAL 8016CB5C's type-2 unlock event, queued through its original data ABI.

8016B08C owns a five-entry inline vector. 8016CDA4 appends type 2;
8016CC0C also sets flag 11. The native result/return flow consumes the vector.
No executable patches, fake physical Ring totals, or forced scene transitions.
"""
from .memory import MemoryUnavailable
from .native_read import APPLICATION_GLOBAL
from ..world_constants import BY_MISSION


def owner(memory, snapshot):
    if snapshot.scene not in ('gameplay','results') or not snapshot.scene_verified or snapshot.stable_polls<3:
        raise MemoryUnavailable('Game Land animation deferred until stable Story gameplay/results')
    if BY_MISSION.get(snapshot.actual_mission,{}).get('zone_index',99)>=6:
        raise MemoryUnavailable('Game Land animation deferred until Story gameplay/results')
    app=memory.read_ptr_checked(APPLICATION_GLOBAL)
    doc=memory.read_ptr_checked(app+4)
    module=memory.read_ptr_checked(doc+0x1c)
    actor=memory.read_ptr_checked(module+0x38,0x98)
    if (memory.read_u32(actor)!=0x8076AC7C or memory.read_u32(actor+0x1c)!=module
            or memory.read_u32(actor+0x64)!=actor+0x70
            or memory.read_u32(actor+0x6c)!=0x80000005):
        raise MemoryUnavailable('Game Land event owner/inline vector mismatch')
    count=memory.read_u32(actor+0x68)
    if count>5:raise MemoryUnavailable('Game Land event queue count invalid')
    return (app,doc,module,actor),count


def prepare(memory,snapshot,owned,slot,journal):
    flags=memory.resolve_flags_ptr()[-1]
    epoch=journal.data.get('bootstrap',{}).get('epoch')
    state=journal.data.get('game_land_notice')
    if not state or state.get('epoch')!=epoch:
        state={'epoch':epoch,'pending':[], 'announced':[], 'state':'idle'}
        journal.data['game_land_notice']=state
    new=[]
    for key,needed in slot['game_land_gates'].items():
        if needed==0:continue  # starter stage needs no unlock notification
        world,act=map(int,key.split('-'));bit=210+(world-1)*3+act-1
        if (owned['red_rings']>=needed and key not in state['announced'] and key not in state['pending']
                and not memory.read_u32(flags+0x10+bit//32*4)&(1<<(bit%32))):new.append(key)
    if new:
        state['pending']+=new;journal.save()
    return state


def apply(memory,snapshot,guard,journal):
    state=journal.data.get('game_land_notice',{})
    if not state.get('pending'):return {'status':'no pending Game Land unlock animation'}
    if state.get('state') in ('publishing','uncertain'):
        # One upgrade retry for the original implementation, which did not
        # distinguish an inactive-slot failure from publication. This affects
        # only a cosmetic notice, never items/checks/gates. Require an empty
        # attributed queue and cleared native notification flag. New recorded
        # count-publication uncertainties are never automatically replayed.
        if 'publish_attempted' not in state and not state.get('legacy_retry_used'):
            guard.check(snapshot)
            _,count=owner(memory,snapshot)
            flags=memory.resolve_flags_ptr()[-1]
            if count==0 and not memory.read_u32(flags+0x10)&(1<<11):
                state.update(state='idle',legacy_retry_used=True);journal.save()
            else:
                return {'status':'legacy event uncertainty retained: queue or notification still active','visual_verified':False}
        else:
            return {'status':'previous native event publication uncertain; no automatic replay',
                    'last_error':state.get('last_error'),'publish_attempted':state.get('publish_attempted'),
                    'visual_verified':False}
    guard.check(snapshot)
    context,count=owner(memory,snapshot);actor=context[-1]
    if count==5:raise MemoryUnavailable('Game Land animation deferred: native queue full')
    if any(memory.read_u32(actor+0x70+i*8)==2 for i in range(count)):
        # Vanilla already supplied the same batched notification.
        state['announced']+=state['pending'];state['pending']=[];journal.save()
        return {'status':'native unlock notification already queued','visual_verified':False}
    chain=memory.resolve_flags_ptr();flags_address=chain[-1]+0x10
    if tuple(snapshot.evidence.get('chain',()))!=chain:
        raise MemoryUnavailable('Game Land notification save attribution changed')
    entry=actor+0x70+count*8
    changes={entry:(memory.read_u32(entry),2),entry+4:(memory.read_u32(entry+4),0),
             flags_address:(memory.read_u32(flags_address),memory.read_u32(flags_address)|(1<<11)),
             actor+0x68:(count,count+1)}
    # Durable intent before publishing. A crash must not silently requeue a
    # cutscene whose native vector may already have been consumed.
    state['state']='publishing';state['publish_attempted']=False;journal.save()
    memory._game_land_notice_transaction=(context,chain,count,changes)
    try:
        for address,(before,after) in changes.items():
            if before!=after:
                if address==actor+0x68:
                    state['publish_attempted']=True;journal.save()
                memory.write_u32(address,after,expected=before,operation='game_land_notice')
    except MemoryUnavailable as error:
        # Inactive vector-slot preparation cannot publish an event. Retry it
        # with freshly verified ownership if count was never attempted.
        state['state']='uncertain' if state['publish_attempted'] else 'idle'
        state['last_error']=str(error)
        journal.save();raise
    finally:memory._game_land_notice_transaction=None
    state['announced']+=state['pending'];state['pending']=[];state['state']='idle';journal.save()
    return {'status':'Vanilla Game Land unlock event type 2 queued; native return flow controls playback',
            'visual_verified':False}
