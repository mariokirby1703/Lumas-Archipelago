from types import SimpleNamespace
import struct
import pytest
from ..Items import ITEM_TABLE,classification
from ..client import native_events as n,dead_weight,event_controls
from ..client.journal import Journal
from ..client.memory import SonicMemory,MemoryUnavailable
from ..client.state import Snapshot,SaveGuard,WritePolicy
from ..client.runtime import Runtime
from .test_memory import FakeBackend
from . import generate


def setup(tmp_path,monkeypatch):
    j=Journal(tmp_path,{'seed':'Test','team':0,'slot':1,'revision':'fixture'})
    j.data['save_identity']='save'
    b=FakeBackend();m=SonicMemory(b);base=0x80002e00
    monkeypatch.setattr(n,'address',lambda memory:base)
    monkeypatch.setattr(m,'verify_revision',lambda:None)
    b.put(base,bytes(n.SIZE));b.put(base,n.MAGIC.to_bytes(4,'big'))
    row={'stage':0x90010000,'player_actor_id':123,'player':{'actor':0x90020000}}
    b.put(0x90020088,(0x90030000).to_bytes(4,'big'))
    s=Snapshot(session='S',stage_epoch='A',save_identity='save',save_identity_verified=True,visible_slot=0,
               scene='gameplay',scene_verified=True,actual_mission='stg110',death_state='alive',stable_polls=3,
               pickup_verified=True,rings_address=0x90040000,lives_address=0x90040004,
               evidence={'native_data':{'stage_objects':[row]}})
    guard=SaveGuard(j);guard.observe(s)
    m.write_guard=WritePolicy(m,guard,lambda memory:s)
    runtime=Runtime(generate().worlds[1].fill_slot_data(),j,guard,SimpleNamespace())
    runtime.snapshot=s
    event_controls.configure(runtime,m)
    return runtime,m,b,base


def test_ack_required_receipt_dedup_and_conflicting_trap_defers(tmp_path,monkeypatch):
    runtime,m,b,base=setup(tmp_path,monkeypatch)
    try:
        item=ITEM_TABLE['Dead Weight Trap']
        dead_weight.deliver(runtime,m,0,item)
        assert runtime.journal.data['effects']['0']['state']=='verifying'
        request=m.read_u32(base+n.TRAP_REQUEST)
        dead_weight.deliver(runtime,m,0,item)
        assert runtime.journal.data['effects']['0']['state']=='verifying'
        b.put(base+n.TRAP_ACK,request.to_bytes(4,'big'))
        dead_weight.deliver(runtime,m,0,item)
        assert runtime.journal.data['effects']['0']['state']=='confirmed'
        count=len(b.writes);dead_weight.deliver(runtime,m,0,item)
        assert len(b.writes)==count
        dead_weight.deliver(runtime,m,1,item)
        assert runtime.journal.data['effects']['1']['state']=='deferred'
        b.put(base+n.REMAINING,bytes(4))
        dead_weight.deliver(runtime,m,1,item)
        assert runtime.journal.data['effects']['1']['state']=='verifying'
    finally:runtime.journal.close()


def test_restart_never_replays_unconfirmed_publication_and_arbitrary_write_blocked(tmp_path,monkeypatch):
    runtime,m,b,base=setup(tmp_path,monkeypatch)
    try:
        item=ITEM_TABLE['Dead Weight Trap'];dead_weight.deliver(runtime,m,0,item)
        del runtime._dead_weight_inflight
        dead_weight.deliver(runtime,m,0,item)
        assert runtime.journal.data['effects']['0']['state']=='uncertain'
        with pytest.raises(MemoryUnavailable,match='transaction'):
            m.write_u32(base+n.REMAINING,0,expected=m.read_u32(base+n.REMAINING),operation='native_event_controls')
        event_controls.write(m,runtime.snapshot,runtime.guard,{n.ENABLE:bytes(4)},disable=True)
        assert m.read_u32(base+n.ENABLE)==0
    finally:runtime.journal.close()


def test_item_id_and_weighted_pool_preserve_progression():
    from ..world_constants import BASE_ID
    assert ITEM_TABLE['Dead Weight Trap']==BASE_ID+54
    assert classification('Dead Weight Trap').trap
    assert generate().worlds[1].options.dead_weight_trap_weight.value==1
    from ..world_constants import load_data
    assert not load_data('versions.json')['live_validation']['dead_weight']
    base={'trap_percentage':100,'ring_loss_trap_weight':'off','score_reset_trap_weight':'off'}
    for value in ('low','medium','high'):
        multi=generate({**base,'dead_weight_trap_weight':value})
        assert any(i.name=='Dead Weight Trap' for i in multi.itempool)
        assert all(i.name=='Dead Weight Trap' for i in multi.itempool if i.trap)
        assert len(multi.itempool)==len(multi.worlds[1].active_locations)
