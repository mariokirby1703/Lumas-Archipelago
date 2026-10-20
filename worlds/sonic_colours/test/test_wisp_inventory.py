from collections import Counter
from types import SimpleNamespace
import struct
import pytest
from ..client import wisp_inventory as w
from ..client.memory import SonicMemory,MemoryUnavailable
from ..client.state import WritePolicy
from ..world_constants import NATIVE_COLOURS,wisp_item
from .test_memory import FakeBackend


@pytest.fixture
def setup(monkeypatch):
    from ..client import movement_gate
    b=FakeBackend();m=SonicMemory(b);actor=0x90001000;stats=0x90002000;model=0x90003000
    def put(a,v):b.put(a,struct.pack('>I',v))
    for a,v in ((actor,0x8075AEF8),(actor+0x8c,stats),(stats,0x8075E088),
                (stats+0x24,0),(stats+0x30,model),(model,0x80763A18)):
        put(a,v)
    b.put(model+8,struct.pack('>fff',42.,6.,10.));b.put(model+0x14,struct.pack('>f',100.))
    b.put(model+0x18,struct.pack('>iiiI',0,0,-1,5));put(model+0x60,0x80)
    for i in range(7):
        ptr=0x90004000+i*4;put(model+0x28+i*8,ptr);b.put(ptr,struct.pack('>f',30.+i))
    state={'current_id':0,'requested_id':-1,'request_machine':0x90005000}
    monkeypatch.setattr(movement_gate,'observed',lambda memory,a:dict(state))
    player={'actor':actor,'stats':stats,'mode':0,'boost_address':model+8,'held_wisp':0}
    snap=SimpleNamespace(scene='gameplay',scene_verified=True,death_state='alive',session='S',stage_epoch=1,
        boost_address=model+8,boost_max_address=model+0x14,evidence={'native_data':{'stage_objects':[{'player':player}]}})
    guard=SimpleNamespace(check_stats=lambda s:('verified fixture owner',))
    # Test the real field/value policy with a fixture-only executable proof.
    m.verify_for_write=lambda operation:None
    m.write_guard=WritePolicy(m,guard,lambda memory:snap)
    return m,b,snap,guard,state,player,model,put


@pytest.mark.parametrize('held',range(7))
@pytest.mark.parametrize('movement',[False,True])
def test_unowned_colour_cleared_with_native_transition_and_boost_preserved(setup,held,movement):
    m,b,snap,guard,state,player,model,put=setup
    put(model+0x18,held);player['held_wisp']=held
    result=w.apply(m,snap,guard,{'counts':Counter()},{'options':{'movement_unlocks':movement}})
    assert result['cleared'] and result['colour']==NATIVE_COLOURS[held]
    assert m.read_s32(model+0x18)==m.read_s32(model+0x1c)==-1
    assert m.read_s32(model+0x20)==-1 and m.read_u32(model+0x24)==0
    assert m.read_f32(model+0xc)==0 and m.read_f32(model+0x10)==0
    assert m.read_f32(model+8)==42. and m.read_f32(model+0x14)==100.
    assert m.read_u32(model+0x60)==0x81
    assert {a for a,_ in b.writes}=={model+0xc,model+0x60}
    assert m._wisp_inventory_transaction is None


@pytest.mark.parametrize('held',range(7))
@pytest.mark.parametrize('movement',[False,True])
def test_first_wisp_unlock_retained_without_second_progressive_copy(setup,held,movement):
    m,b,snap,guard,state,player,model,put=setup
    put(model+0x18,held);player['held_wisp']=held
    counts=Counter({wisp_item(NATIVE_COLOURS[held],movement):1})
    assert not w.apply(m,snap,guard,{'counts':counts},{'options':{'movement_unlocks':movement}})['cleared']
    assert not b.writes


@pytest.mark.parametrize('current,requested',[(64,-1),(0,64),(24,-1),(112,-1)])
def test_transform_and_death_transitions_defer_without_writes(setup,current,requested):
    m,b,snap,guard,state,player,model,put=setup
    state.update(current_id=current,requested_id=requested)
    with pytest.raises(MemoryUnavailable):w.apply(m,snap,guard,{'counts':Counter()},{'options':{}})
    assert not b.writes


@pytest.mark.parametrize('state_id',[0,5,18,37,42])
def test_normal_movement_including_rails_does_not_retain_a_locked_wisp(setup,state_id):
    m,b,snap,guard,state,player,model,put=setup
    state.update(current_id=state_id)
    assert w.apply(m,snap,guard,{'counts':Counter()},{'options':{}})['cleared']


def test_empty_inventory_no_repeat_and_guard_blocks_other_stats(setup):
    m,b,snap,guard,state,player,model,put=setup
    assert w.apply(m,snap,guard,{'counts':Counter()},{'options':{}})['cleared']
    before=len(b.writes);player['held_wisp']=-1
    assert not w.apply(m,snap,guard,{'counts':Counter()},{'options':{}})['cleared']
    assert len(b.writes)==before
    with pytest.raises(MemoryUnavailable):m.write_u32(model+8,0,expected=m.read_u32(model+8),operation='wisp_inventory')
    assert m.read_f32(model+8)==42.


def test_unnotified_empty_slot_retries_redraw_without_replaying_inventory_clear(setup,monkeypatch):
    m,b,snap,guard,state,player,model,put=setup
    original=m.write_u32
    def fail(*a,**kw):raise MemoryUnavailable('native scene changed before redraw')
    monkeypatch.setattr(m,'write_u32',fail)
    with pytest.raises(MemoryUnavailable):w.apply(m,snap,guard,{'counts':Counter()},{'options':{}})
    assert m.read_s32(model+0x18)==-1
    player['held_wisp']=-1;monkeypatch.setattr(m,'write_u32',original)
    w.apply(m,snap,guard,{'counts':Counter()},{'options':{}})
    assert m.read_u32(model+0x60)==0x81
    assert len(b.writes)==2 and m._wisp_inventory_pending_redraw is None


def test_replaced_model_and_assist_are_not_written(setup):
    m,b,snap,guard,state,player,model,put=setup
    player['mode']=2
    with pytest.raises(MemoryUnavailable):w.apply(m,snap,guard,{'counts':Counter()},{'options':{}})
    player['mode']=0;put(player['stats']+0x30,model+0x100)
    with pytest.raises(MemoryUnavailable):w.apply(m,snap,guard,{'counts':Counter()},{'options':{}})
    assert not b.writes


@pytest.mark.parametrize('colour',range(7))
@pytest.mark.parametrize('state_id',[0,97])
def test_empty_main_slot_still_clears_unowned_hud_residue(setup,colour,state_id):
    m,b,snap,guard,state,player,model,put=setup
    player['held_wisp']=-1
    b.put(model+0x18,struct.pack('>iiiI',-1,-1,colour,0))
    b.put(model+0x10,struct.pack('>f',0.))
    state.update(current_id=state_id,requested_id=state_id)
    put(player['stats']+0x10,0x00200a00)
    assert w.apply(m,snap,guard,{'counts':Counter()},{'options':{}})['cleared']
    assert struct.unpack('>3i',m.read_bytes(model+0x18,12))==(-1,-1,-1)
    assert m.read_f32(model+8)==42. and m.read_f32(model+0x14)==100.
    writes=len(b.writes)
    assert not w.apply(m,snap,guard,{'counts':Counter()},{'options':{}})['cleared']
    assert len(b.writes)==writes


@pytest.mark.parametrize('condition',['dry','active_timer','pending_wisp','current_wisp','transform_request'])
def test_underwater_exception_only_allows_inert_display_residue(setup,condition):
    m,b,snap,guard,state,player,model,put=setup
    player['held_wisp']=-1
    b.put(model+0x18,struct.pack('>iiiI',-1,-1,0,0));b.put(model+0x10,struct.pack('>f',0.))
    put(player['stats']+0x10,0x800);state.update(current_id=97,requested_id=97)
    if condition=='dry':put(player['stats']+0x10,0)
    elif condition=='active_timer':b.put(model+0x10,struct.pack('>f',1.))
    elif condition=='pending_wisp':put(model+0x1c,0)
    elif condition=='current_wisp':put(model+0x18,0)
    else:state['requested_id']=64
    with pytest.raises(MemoryUnavailable):w.apply(m,snap,guard,{'counts':Counter()},{'options':{}})
    assert not b.writes


def test_owned_pending_wisp_is_not_discarded_to_clear_old_locked_icon(setup):
    m,b,snap,guard,state,player,model,put=setup
    b.put(model+0x18,struct.pack('>iiiI',-1,1,0,0))
    counts=Counter({'Cyan Laser Wisp':1})
    assert not w.apply(m,snap,guard,{'counts':counts},{'options':{}})['cleared']
    assert not b.writes
