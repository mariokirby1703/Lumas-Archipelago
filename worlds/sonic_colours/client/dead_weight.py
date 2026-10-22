"""Fifteen gameplay seconds of Jump denial, with guest countdown and ACK."""
import struct
from . import native_events as n
from .event_controls import write
from .memory import MemoryUnavailable

DURATION=15.


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
    effect.update(family='dead_weight',native_request=request);journal.save()
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
    return request
