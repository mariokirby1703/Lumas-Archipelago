import math
import struct
import pytest
from ..client import water_native as w,movement_gate
from ..client.memory import SonicMemory,MemoryUnavailable
from .test_memory import FakeBackend


def fixture(monkeypatch):
    b=FakeBackend();m=SonicMemory(b)
    machine,collection,plugin=0x90010000,0x90020000,0x90030000
    node=collection+0x20
    monkeypatch.setattr(movement_gate,'observed',lambda memory,player:{'request_machine':machine})
    for address,value in ((machine+0x34,collection),(collection+0xc,node),
                          (node+4,collection+8),(node+8,plugin),(plugin,w.VTABLE),(plugin+8,w.NAME)):
        b.put(address,value.to_bytes(4,'big'))
    for address,value in ((w.TOTAL_ADDRESS,30.0),(w.WARNING_ADDRESS,13.0),(plugin+0x20,20.4336)):
        b.put(address,struct.pack('>f',value))
    return m,b,machine,collection,node,plugin


def test_native_oxygen_math_and_read_only(monkeypatch):
    m,b,_,_,_,plugin=fixture(monkeypatch)
    result=w.read(m,0x90040000)
    assert result['remaining_seconds']==pytest.approx(9.5664,abs=.00001)
    assert result['native_warning_phase'] and not result['write_verified']
    assert result['elapsed_address']==plugin+0x20 and not b.writes


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-31.0,999.0])
def test_unsafe_float_is_not_a_clock(monkeypatch,value):
    m,b,_,_,_,plugin=fixture(monkeypatch)
    b.put(plugin+0x20,struct.pack('>f',value))
    with pytest.raises(MemoryUnavailable):w.read(m,0x90040000)
    assert not b.writes


def test_collection_cycle_and_wrong_class_rejected(monkeypatch):
    m,b,_,_,node,plugin=fixture(monkeypatch)
    b.put(node+4,node.to_bytes(4,'big'))
    with pytest.raises(MemoryUnavailable,match='cycle'):w.read(m,0x90040000)
    b.put(plugin,(w.VTABLE+4).to_bytes(4,'big'))
    with pytest.raises(MemoryUnavailable,match='vtable'):w.read(m,0x90040000)


def writable_fixture(monkeypatch):
    from types import SimpleNamespace
    from ..client.state import WritePolicy
    m,b,_,_,_,plugin=fixture(monkeypatch)
    player=0x90040000;stats=0x90050000
    b.put(player+0x8c,stats.to_bytes(4,'big'));b.put(stats,(0x8075E088).to_bytes(4,'big'))
    b.put(stats+0x10,(0x800).to_bytes(4,'big'))
    snapshot=SimpleNamespace(scene='gameplay',death_state='alive',stable_polls=3,
        session='session',stage_epoch='stage',evidence={'native_data':{'stage_objects':[{'player':{'actor':player}}]}})
    guard=SimpleNamespace(check_stats=lambda snapshot:None,can_record_pickups=lambda snapshot:True)
    monkeypatch.setattr(m,'verify_revision',lambda:None)
    m.write_guard=WritePolicy(m,guard,lambda memory:snapshot)
    b.put(plugin+0x20,struct.pack('>f',0.25))
    return m,b,plugin,snapshot,guard


def test_warning_floor_once_then_native_clock_continues(monkeypatch):
    m,b,plugin,snapshot,guard=writable_fixture(monkeypatch)
    snapshot.stable_polls=1  # no multi-poll delay after attributed water entry
    result=w.configure(m,snapshot,guard,{'counts':{'Breath':0}})
    assert result['write_verified']
    assert m.read_f32(plugin+0x20)==pytest.approx(30.05)
    writes=len(b.writes)
    w.configure(m,snapshot,guard,{'counts':{'Breath':0}})
    assert len(b.writes)==writes
    # Native bubble reset gets the same shortened supply; never overwrite an
    # already running countdown or invoke a death transition ourselves.
    b.put(plugin+0x20,struct.pack('>f',0))
    w.configure(m,snapshot,guard,{'counts':{'Breath':0}})
    assert len(b.writes)==writes+1


def test_breath_owned_and_unsafe_scene_do_not_write(monkeypatch):
    m,b,plugin,snapshot,guard=writable_fixture(monkeypatch)
    w.configure(m,snapshot,guard,{'counts':{'Breath':1}})
    assert not b.writes


def test_unattributed_playthrough_cannot_shorten_air(monkeypatch):
    m,b,plugin,snapshot,guard=writable_fixture(monkeypatch)
    guard.can_record_pickups=lambda snapshot:False
    result=w.configure(m,snapshot,guard,{'counts':{'Breath':0}})
    assert 'authenticated' in result['status'] and not b.writes
    guard.can_record_pickups=lambda snapshot:True
    snapshot.scene='results'
    w.configure(m,snapshot,guard,{'counts':{'Breath':0}})
    assert not b.writes


def test_breath_policy_rejects_arbitrary_timer_values(monkeypatch):
    m,b,plugin,snapshot,guard=writable_fixture(monkeypatch)
    before=struct.pack('>f',0.25);after=struct.pack('>f',129.9)
    m._breath_transaction=(0x90040000,plugin,before,after)
    with pytest.raises(MemoryUnavailable,match='bounded progressive duration'):
        m.write_bytes_verified(plugin+0x20,after,expected=before,operation='breath_timer')
    assert not b.writes


def test_advancing_clock_during_policy_verification_does_not_block_floor(monkeypatch):
    m,b,plugin,snapshot,guard=writable_fixture(monkeypatch)
    original=m.write_guard
    def advancing(operation,address,size):
        token=original(operation,address,size)
        b.put(plugin+0x20,struct.pack('>f',m.read_f32(plugin+0x20)+0.02))
        return token
    m.write_guard=advancing
    w.configure(m,snapshot,guard,{'counts':{'Breath':0}})
    assert m.read_f32(plugin+0x20)>=30.05 and len(b.writes)==1


@pytest.mark.parametrize('count,seconds',list(enumerate((0,5,10,20,40,60))))
def test_progressive_air_stages_use_original_death_deadline(monkeypatch,count,seconds):
    m,b,plugin,snapshot,guard=writable_fixture(monkeypatch)
    result=w.configure(m,snapshot,guard,{'counts':{'Progressive Breathing':count}})
    remaining=w.read(m,0x90040000)['remaining_seconds']
    assert result['air_seconds']==seconds
    assert remaining==pytest.approx(max(0,seconds-0.25),abs=0.01)
    count_writes=len(b.writes)
    w.configure(m,snapshot,guard,{'counts':{'Progressive Breathing':count}})
    assert len(b.writes)==count_writes


def test_sixty_second_air_can_cross_native_zero_without_refilling(monkeypatch):
    m,b,plugin,snapshot,guard=writable_fixture(monkeypatch)
    owned={'counts':{'Progressive Breathing':5}}
    w.configure(m,snapshot,guard,owned)
    b.put(plugin+0x20,struct.pack('>f',-0.2))
    w.configure(m,snapshot,guard,owned)
    b.put(plugin+0x20,struct.pack('>f',-0.02))
    w.configure(m,snapshot,guard,owned)
    b.put(plugin+0x20,struct.pack('>f',0.02))
    writes=len(b.writes);w.configure(m,snapshot,guard,owned)
    assert len(b.writes)==writes


def test_breath_upgrade_preserves_time_already_spent_underwater(monkeypatch):
    m,b,plugin,snapshot,guard=writable_fixture(monkeypatch)
    w.configure(m,snapshot,guard,{'counts':{'Progressive Breathing':1}})
    b.put(plugin+0x20,struct.pack('>f',27)) # three seconds of initial five remain
    w.configure(m,snapshot,guard,{'counts':{'Progressive Breathing':2}})
    assert m.read_f32(plugin+0x20)==22 # ten-second supply minus two spent


def test_bubble_reset_detected_after_near_zero_window_was_missed(monkeypatch):
    m,b,plugin,snapshot,guard=writable_fixture(monkeypatch)
    owned={'counts':{'Progressive Breathing':1}}
    w.configure(m,snapshot,guard,owned)
    b.put(plugin+0x20,struct.pack('>f',1.966666))
    result=w.configure(m,snapshot,guard,owned)
    assert result['write_verified']
    assert m.read_f32(plugin+0x20)==pytest.approx(26.966666,abs=0.001)
    writes=len(b.writes)
    w.configure(m,snapshot,guard,owned)
    assert len(b.writes)==writes


def test_client_restart_does_not_grant_sixty_seconds_again(monkeypatch):
    from types import SimpleNamespace
    m,b,plugin,snapshot,guard=writable_fixture(monkeypatch)
    journal=SimpleNamespace(data={},save=lambda:None)
    owned={'counts':{'Progressive Breathing':5}}
    w.configure(m,snapshot,guard,owned,journal)
    b.put(plugin+0x20,struct.pack('>f',-20))
    del m._oxygen_records
    writes=len(b.writes)
    w.configure(m,snapshot,guard,owned,journal)
    assert len(b.writes)==writes and m.read_f32(plugin+0x20)==-20


def test_reused_heap_in_new_dolphin_process_gets_fresh_air(monkeypatch):
    from types import SimpleNamespace
    m,b,plugin,snapshot,guard=writable_fixture(monkeypatch)
    pid=[100]
    b.instance_info=lambda:{'process_candidates':[{'pid':pid[0]}]}
    b.assert_instance=lambda info:None
    journal=SimpleNamespace(data={},save=lambda:None)
    owned={'counts':{'Progressive Breathing':4}}
    w.configure(m,snapshot,guard,owned,journal)
    pid[0]=200
    b.put(plugin+0x20,struct.pack('>f',1))
    del m._oxygen_records
    w.configure(m,snapshot,guard,owned,journal)
    assert m.read_f32(plugin+0x20)==-9


def test_same_heap_new_respawn_gets_fresh_air(monkeypatch):
    m,b,plugin,snapshot,guard=writable_fixture(monkeypatch)
    owned={'counts':{'Progressive Breathing':5}}
    stage=snapshot.evidence['native_data']['stage_objects'][0]
    stage.update(stage=0x90060000,death_count=0)
    w.configure(m,snapshot,guard,owned)
    stage['death_count']=1;b.put(plugin+0x20,struct.pack('>f',0.1))
    w.configure(m,snapshot,guard,owned)
    assert m.read_f32(plugin+0x20)==pytest.approx(-29.9,abs=.0001)
