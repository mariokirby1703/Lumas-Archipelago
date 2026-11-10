from types import SimpleNamespace
import pytest
from ..client import score_reset
from ..client.memory import SonicMemory,MemoryUnavailable
from ..client.native_read import STAGE_VTABLE
from ..client.state import WritePolicy
from ..Items import ITEM_TABLE
from .test_memory import FakeBackend


def setup(monkeypatch):
    backend=FakeBackend();memory=SonicMemory(backend);stage=0x90010000
    backend.put(stage,STAGE_VTABLE.to_bytes(4,'big'))
    backend.put(stage+0x80,(500).to_bytes(4,'big'))
    backend.put(stage+0x198,b'KEEP')
    backend.put(stage+0x19c,b''.join((100+i).to_bytes(4,'big') for i in range(21)))
    snap=SimpleNamespace(scene='gameplay',scene_verified=True,actual_mission='stg110',session='session',stage_epoch='stage',
        evidence={'native_data':{'stage_objects':[{'stage':stage,'mission':'stg110'}]}})
    guard=SimpleNamespace(check_stats=lambda snapshot:None)
    monkeypatch.setattr(memory,'verify_revision',lambda:None)
    memory.write_guard=WritePolicy(memory,guard,lambda m:snap)
    data={'effects':{}}
    def prepare(i,item,context,before,after):data['effects'][str(i)]={'state':'prepared','before':before,'after':after}
    def confirm(i,**kw):data['effects'][str(i)]['state']='confirmed'
    journal=SimpleNamespace(data=data,prepare=prepare,confirm=confirm,save=lambda:None,defer=lambda *a:None)
    return memory,backend,stage,snap,guard,journal


def test_reset_clears_all_live_sources_and_preserves_accumulator_header(monkeypatch):
    memory,backend,stage,snap,guard,journal=setup(monkeypatch)
    score_reset.deliver(memory,snap,guard,journal,0,ITEM_TABLE['Score Reset Trap'])
    assert memory.read_u32(stage+0x80)==0
    assert memory.read_bytes(stage+0x19c,84)==bytes(84)
    assert memory.read_bytes(stage+0x198,4)==b'KEEP'
    assert journal.data['effects']['0']['state']=='confirmed'
    assert len(backend.writes)==2


def test_unknown_stage_type_and_unplanned_write_are_blocked(monkeypatch):
    memory,backend,stage,snap,guard,journal=setup(monkeypatch)
    with pytest.raises(MemoryUnavailable,match='transaction'):
        memory.write_bytes_verified(stage+0x80,bytes(4),expected=(500).to_bytes(4,'big'),operation='score_reset')
    backend.put(stage,bytes(4))
    with pytest.raises(MemoryUnavailable,match='ownership'):score_reset.sources(memory,snap)
    assert not backend.writes


@pytest.mark.parametrize('mission',['stg110','stg190','stg790','stgD10','stgG30'])
def test_native_delivery_requires_ack_and_never_repeats_completed_reset(tmp_path,monkeypatch,mission):
    from dataclasses import replace
    from .test_dead_weight import setup as live_setup
    from ..client import native_events as n
    runtime,m,b,base=live_setup(tmp_path,monkeypatch)
    try:
        m.native_patch={'native_score_reset':True}
        b.put(base+n.INPUT,bytes(4))
        runtime.snapshot=replace(runtime.snapshot,actual_mission=mission)
        row=runtime.snapshot.evidence['native_data']['stage_objects'][0]
        row['mission']=mission;stage=row['stage']
        b.put(stage,STAGE_VTABLE.to_bytes(4,'big'));b.put(stage+0x80,(600).to_bytes(4,'big'))
        b.put(stage+0x19c,bytes(84))
        item=ITEM_TABLE['Score Reset Trap']
        score_reset.deliver(m,runtime.snapshot,runtime.guard,runtime.journal,0,item)
        effect=runtime.journal.data['effects']['0'];request=effect['native_request']
        assert effect['state']=='verifying' and m.read_u32(stage+0x80)==600
        writes=len(b.writes)
        score_reset.deliver(m,runtime.snapshot,runtime.guard,runtime.journal,0,item)
        assert len(b.writes)==writes
        b.put(base+n.INPUT,((request<<16)|request).to_bytes(4,'big'))
        # Score earned after native acknowledgement must survive reconciliation.
        b.put(stage+0x80,(100).to_bytes(4,'big'))
        effect['state']='uncertain'
        score_reset.deliver(m,runtime.snapshot,runtime.guard,runtime.journal,0,item)
        assert effect['state']=='confirmed' and m.read_u32(stage+0x80)==100
        assert len(b.writes)==writes
    finally:runtime.journal.close()


def test_legacy_prewrite_failure_is_deferred_instead_of_lost(monkeypatch):
    memory,backend,stage,snap,guard,journal=setup(monkeypatch)
    def blocked(*a,**kw):raise MemoryUnavailable('WRITE_BLOCKED: compare_failed')
    monkeypatch.setattr(memory,'write_bytes_verified',blocked)
    score_reset.deliver(memory,snap,guard,journal,0,ITEM_TABLE['Score Reset Trap'])
    assert journal.data['effects']['0']['state']=='deferred'
    assert not backend.writes


def test_event_owner_refresh_preserves_native_score_request(tmp_path,monkeypatch):
    from .test_dead_weight import setup as live_setup
    from ..client import native_events as n,event_controls
    runtime,m,b,base=live_setup(tmp_path,monkeypatch)
    try:
        m.native_patch={'native_score_reset':True}
        b.put(base+n.INPUT,((7<<16)|6).to_bytes(4,'big'))
        runtime._event_owner=None
        event_controls.configure(runtime,m)
        assert m.read_u32(base+n.INPUT)==(7<<16)|6
    finally:runtime.journal.close()


def test_native_ack_during_publication_readback_is_a_success(tmp_path,monkeypatch):
    from .test_dead_weight import setup as live_setup
    from ..client import native_events as n
    runtime,m,b,base=live_setup(tmp_path,monkeypatch)
    try:
        m.native_patch={'native_score_reset':True};b.put(base+n.INPUT,bytes(4))
        row=runtime.snapshot.evidence['native_data']['stage_objects'][0];row['mission']='stg110'
        stage=row['stage'];b.put(stage,STAGE_VTABLE.to_bytes(4,'big'))
        b.put(stage+0x80,(600).to_bytes(4,'big'));b.put(stage+0x19c,bytes(84))
        original=b.write_bytes
        def write(address,raw):
            original(address,raw)
            if address==base+n.INPUT:
                request=int.from_bytes(raw,'big')>>16
                b.put(stage+0x80,bytes(4))
                b.put(address,((request<<16)|request).to_bytes(4,'big'))
        monkeypatch.setattr(b,'write_bytes',write)
        item=ITEM_TABLE['Score Reset Trap']
        score_reset.deliver(m,runtime.snapshot,runtime.guard,runtime.journal,0,item)
        assert runtime.journal.data['effects']['0']['state']=='verifying'
        score_reset.deliver(m,runtime.snapshot,runtime.guard,runtime.journal,0,item)
        assert runtime.journal.data['effects']['0']['state']=='confirmed'
        assert m.read_u32(stage+0x80)==0
    finally:runtime.journal.close()


def test_proven_unwritten_legacy_failure_can_be_delivered_natively(tmp_path,monkeypatch):
    from .test_dead_weight import setup as live_setup
    from ..client import native_events as n
    runtime,m,b,base=live_setup(tmp_path,monkeypatch)
    try:
        m.native_patch={'native_score_reset':True};b.put(base+n.INPUT,bytes(4))
        row=runtime.snapshot.evidence['native_data']['stage_objects'][0];row['mission']='stg110'
        stage=row['stage'];b.put(stage,STAGE_VTABLE.to_bytes(4,'big'))
        b.put(stage+0x80,(600).to_bytes(4,'big'));b.put(stage+0x19c,bytes(84))
        runtime.journal.data['effects']['0']={'state':'uncertain','family':'score','completed_writes':0,
            'reason':'WRITE_BLOCKED: compare_failed'}
        score_reset.deliver(m,runtime.snapshot,runtime.guard,runtime.journal,0,ITEM_TABLE['Score Reset Trap'])
        assert runtime.journal.data['effects']['0']['state']=='verifying'
        assert m.read_u32(base+n.INPUT)>>16>0
    finally:runtime.journal.close()
