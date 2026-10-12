"""Guarded original-data spawn edit; no claim of live collision success."""
from dataclasses import replace
import struct
import pytest
from ..client import intro_box as b
from ..client.memory import SonicMemory,MemoryUnavailable
from ..client.state import Snapshot,PlaythroughState,WritePolicy
from .test_memory import FakeBackend


def fixture(monkeypatch):
    m=SonicMemory(FakeBackend());base=0x90010000;actor=0x90030000;wrapper=0x90031000
    spec=b.SPEC;ident,off,cls=next(x for x in spec['anchors'] if x[1]!=spec['record_offset'])
    def put(a,value):m.backend.write_bytes(a,value.to_bytes(4,'big'))
    for a,v in ((actor+0x64,wrapper),(wrapper+4,actor),(wrapper+8,base+off),
        (base+off,ident),(base+off+4,cls),(base,spec['file_size']),
        (base+0x28,spec['dict_count']),(base+0x38,spec['object_count']),
        (base+0x40,spec['instance_count']),(base+spec['record_offset'],spec['object_id']),
        (base+spec['record_offset']+4,spec['class_id']),
        (base+spec['record_offset']+0x18,base+spec['vector_offset']),
        (base+spec['record_offset']+0x1c,1)):put(a,v)
    m.backend.write_bytes(base+0x18,b'BINA');m.backend.write_bytes(base+0x20,b'SOBJ')
    m.backend.write_bytes(base+spec['vector_offset'],struct.pack('>3f',*spec['position']))
    actors=[actor];monkeypatch.setattr('worlds.sonic_colours.client.native_read.read_actors',lambda *args:list(actors))
    s=Snapshot('session',None,None,'gameplay','stg130',stage_epoch='intro2',stable_polls=3,
        scene_verified=True,death_state='alive',evidence={'native_data':{'stage_objects':[{'mission':'stg130','context':0x90050000}]}})
    class Guard:
        state=PlaythroughState.MANDATORY_PROLOGUE
        def can_record_pickups(self,s):return True
    guard=Guard();m.verify_revision=lambda:None
    m.write_guard=WritePolicy(m,guard,lambda _:s)
    return m,s,guard,base,actors,put


def test_native_spawn_vector_is_lifted_once_and_restored_in_replay(monkeypatch):
    m,s,g,base,actors,put=fixture(monkeypatch);slot={'options':{'movement_unlocks':1}}
    before=dict(m.backend.data);a=base+b.SPEC['vector_offset']+4
    assert b.apply(m,s,g,slot)['applied']
    assert m.read_bytes(a,4)==b.RAISED
    assert {p for p in m.backend.data if m.backend.data[p]!=before.get(p)} <= set(range(a,a+4))
    assert b.apply(m,s,g,slot)['applied']
    g.state=PlaythroughState.BOUND_PLAYTHROUGH
    assert b.apply(m,replace(s,save_identity='bound save'),g,slot)['applied']
    assert not b.apply(m,s,g,{'options':{'movement_unlocks':0}})['applied']
    assert m.read_bytes(a,4)==b.ORIGINAL


def test_existing_box_or_corrupt_resource_never_gets_moved(monkeypatch):
    m,s,g,base,actors,put=fixture(monkeypatch)
    actor=0x90032000;w=0x90033000
    put(actor+0x64,w);put(w+4,actor);put(w+8,base+b.SPEC['record_offset']);actors.append(actor)
    before=dict(m.backend.data)
    result=b.apply(m,s,g,{'options':{'movement_unlocks':1}})
    assert 'already constructed' in result['status']
    assert m.backend.data==before
    actors.pop();put(base+b.SPEC['record_offset']+4,0)
    with pytest.raises(MemoryUnavailable):b.apply(m,s,g,{'options':{'movement_unlocks':1}})


def test_replay_write_remains_bounded_and_requires_attribution(monkeypatch):
    m,s,g,base,actors,put=fixture(monkeypatch);a=base+b.SPEC['vector_offset']+4
    g.state=PlaythroughState.BOUND_PLAYTHROUGH
    m.write_bytes_verified(a,b.RAISED,expected=b.ORIGINAL,operation='intro_box_placement')
    m.write_bytes_verified(a,b.ORIGINAL,expected=b.RAISED,operation='intro_box_placement')
    monkeypatch.setattr(g,'can_record_pickups',lambda _:False)
    with pytest.raises(MemoryUnavailable,match='not attributed'):
        m.write_bytes_verified(a,b.RAISED,expected=b.ORIGINAL,operation='intro_box_placement')
    with pytest.raises(MemoryUnavailable,match='bounded placement'):
        m.write_bytes_verified(a,struct.pack('>f',0),expected=b.ORIGINAL,operation='intro_box_placement')
    assert m.read_bytes(a,4)==b.ORIGINAL


def test_previous_twenty_unit_lift_is_migrated_before_construction(monkeypatch):
    m,s,g,base,actors,put=fixture(monkeypatch)
    address=base+b.SPEC['vector_offset']+4
    m.backend.write_bytes(address,b.PREVIOUS_RAISED)
    result=b.apply(m,s,g,{'options':{'movement_unlocks':1}})
    assert result['lift']==15.0
    assert m.read_f32(address)==b.SPEC['position'][1]+15.0
    assert m.read_bytes(address,4)==b.RAISED
