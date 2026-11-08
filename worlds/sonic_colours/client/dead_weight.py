import struct
import time
from . import native_events as n
from .event_controls import write
from .memory import MemoryUnavailable

DURATION=10.


def deliver(runtime,memory,index,item):
    journal=runtime.journal;effect=journal.data['effects'].get(str(index),{})
    state=n.status(memory)
    runtime.temporary_trap_status={'name':'Dead Weight Trap','remaining':state['remaining'],
                                 'request':state['trap_request'],'ack':state['trap_ack']}
    if effect.get('state') in ('confirmed','uncertain','skipped_by_operator'):return
    if effect.get('state') in ('prepared','verifying'):
        if effect.get('native_request')==state['trap_ack']:
            journal.confirm(index,verified_delivery=True)
        elif getattr(runtime,'_dead_weight_inflight',None)!=index:
            effect.update(state='uncertain',reason='client restarted during native trap publication; never replay')
            journal.save()
        return
    runtime.guard.check_stats(runtime.snapshot)
    if state['remaining']>0:
        journal.defer(index,item,'previous Dead Weight Trap still active');return
    request=(state['trap_request']+1)&0xffffffff or 1
    journal.prepare(index,item,[runtime.snapshot.session,runtime.snapshot.stage_epoch],0,DURATION)
    effect=journal.data['effects'][str(index)]
    effect.update(family='dead_weight',native_request=request,expires_at=time.time()+DURATION);journal.save()
    try:
        write(memory,runtime.snapshot,runtime.guard,{n.REMAINING:struct.pack('>f',DURATION)})
        write(memory,runtime.snapshot,runtime.guard,{n.TRAP_REQUEST:struct.pack('>I',request)})
        effect['state']='verifying';journal.save();runtime._dead_weight_inflight=index
    except MemoryUnavailable as error:
        effect.update(state='uncertain',reason=str(error));journal.save()


def test_request(runtime,memory):
    """Explicit local developer test. Never creates an AP receipt."""
    state=n.status(memory)
    if state['remaining']>0:raise MemoryUnavailable('Dead Weight already active')
    request=(state['trap_request']+1)&0xffffffff or 1
    write(memory,runtime.snapshot,runtime.guard,{n.REMAINING:struct.pack('>f',DURATION)})
    write(memory,runtime.snapshot,runtime.guard,{n.TRAP_REQUEST:struct.pack('>I',request)})
    runtime._dead_weight_test_clock=(request,time.time()+DURATION)
    return request


def tick(runtime,memory):
    state=n.status(memory)
    if state['remaining']<=0:return
    request=state['trap_request']
    effect=next((e for e in runtime.journal.data['effects'].values()
                 if e.get('family')=='dead_weight' and e.get('native_request')==request
                 and e.get('state') in ('prepared','verifying','confirmed')),None)
    if effect is None:
        test=getattr(runtime,'_dead_weight_test_clock',None)
        if not test or test[0]!=request:return
        effect={'expires_at':test[1]}
    if 'expires_at' not in effect:
        effect['expires_at']=time.time()+min(DURATION,state['remaining'])
        runtime.journal.save()
    remaining=min(state['remaining'],max(0.,effect['expires_at']-time.time()))
    if remaining>=state['remaining']:return
    base=n.address(memory);address=base+n.REMAINING;raw=struct.pack('>f',remaining)
    memory._event_transaction={'allowed':{address:4},'trap_clock':request,
                              'values':{n.REMAINING:raw}}
    try:
        memory.write_bytes_verified(address,raw,expected=struct.pack('>f',state['remaining']),
                                    operation='native_event_controls')
    finally:memory._event_transaction=None
