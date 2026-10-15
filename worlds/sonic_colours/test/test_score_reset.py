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
