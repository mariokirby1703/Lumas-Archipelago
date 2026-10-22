import struct
import pytest
from ..client import rail_actions as r,native_events as n,movement_gate as g
from ..client.native_dol import plan,Dol,patch_dol
from .test_native_events import Machine


def machine(monkeypatch,kind,mask,held=0):
    rows=r.planned_patches();hooks=plan()[3]
    m=Machine('death');m.kind='rail_'+kind
    hook,original,_=r.HOOKS[kind]
    monkeypatch.setitem(n.HOOKS,m.kind,(hook,original))
    for address,old,new in rows:m.b.put(address,new)
    state=0x900a0000;owner=0x900b0000;player=0x900c0000;holder=0x900d0000;inputs=0x900e0000
    control=next(h for h in hooks if h['hook']==g.HOOK)['target']+g.payload(gecko=True)[2]
    for address,value in ((state,r.GRIND_VTABLE),(owner,g.STATE_MACHINE_VTABLE),
                          (owner+0x28,player),(player,g.PLAYER_VTABLE),(player+0x70,holder),
                          (holder+8,owner),(player+0x88,inputs),(inputs+0x4c,held),
                          (control,1),(control+4,mask)):
        m.put(address,value)
    m.r[3]=state;m.r[4]=owner;m.before=m.r[:]
    return m,control,state,owner,player,inputs


@pytest.mark.parametrize('kind',['jump','switch'])
@pytest.mark.parametrize('mask',[0,4,512,1024,1536,16383])
@pytest.mark.parametrize('held',[0,4,8,12])
def test_independent_rail_permissions_cover_held_and_alternate_jump_trigger(monkeypatch,kind,mask,held):
    m,control,state,owner,player,inputs=machine(monkeypatch,kind,mask,held)
    required=r.HOOKS[kind][2]|(1024 if kind=='jump' and held&12 else 0)
    allowed=mask&required==required
    for _ in range(5):
        m.r=m.before[:];m.run()
        assert not m.calls and m.lr==0x80001234 and m.ctr==0x80005678 and m.f==m.before_f
        assert m.r[4:]==m.before[4:]
        assert m.get(inputs+0x4c)==held
        if allowed:assert m.r[3]==state and m.r[1]==m.before[1]-0x10
        else:assert m.r[3]==0 and m.r[1]==m.before[1]
    assert all(m.before[1]-0x20<=a<m.before[1] for a,data in m.b.writes)


@pytest.mark.parametrize('kind',['jump','switch'])
@pytest.mark.parametrize('case',['unarmed','other_state','other_machine','other_player','backref'])
def test_unrelated_or_unverified_context_uses_native_helper(monkeypatch,kind,case):
    m,control,state,owner,player,inputs=machine(monkeypatch,kind,0)
    if case=='unarmed':m.put(control,0)
    elif case=='other_state':m.put(state,0)
    elif case=='other_machine':m.put(owner,0)
    elif case=='other_player':m.put(player,0)
    else:m.put(m.get(player+0x70)+8,owner+4)
    m.run();assert m.r[3]==state and m.r[1]==m.before[1]-0x10


def test_native_input_routes_and_padding_are_byte_verified():
    from ..tools.private_assets import reference_root
    from ..world_constants import load_data
    raw=(reference_root()/'memdumps_and_more/main.dol').read_bytes();im=Dol(raw)
    assert im.read(0x800ca2c4,4)==struct.pack('>I',r.HOOKS['jump'][1])
    # Both press and alternate jump query occur AFTER our helper entry gate.
    for address,target in ((0x800ca2e0,0x8020afe8),(0x800ca2f0,0x8020b1e0)):
        word=int.from_bytes(im.read(address,4),'big');delta=word&0x3fffffc
        if delta&0x2000000:delta-=0x4000000
        assert word>>26==18 and address+delta==target
    assert im.read(0x800ca300,4)==bytes.fromhex('3880001d')
    assert im.read(0x800ca29c,4)==bytes.fromhex('3880001e')
    refs=set()
    for index,offset,base,size in im.sections:
        for i in range(0,size-3,4):
            word=struct.unpack_from('>I',im.data,offset+i)[0];refs.add(word)
            if index<7 and word>>26 in (16,18):
                mask,sign=(0xfffc,0x8000) if word>>26==16 else (0x3fffffc,0x2000000)
                delta=word&mask
                if delta&sign:delta-=sign*2
                refs.add(delta if word&2 else base+i+delta)
    for site in load_data('rail_action_sites.json'):
        address=site['address'];before=int(site['before'],16)
        assert im.read(address-4,16)==struct.pack('>I',before)+bytes(12)
        assert before==0x4e800020 or before>>26==18 and not before&1
        assert not any(address+i in refs for i in range(12))
    for address,old,new in r.planned_patches():assert im.read(address,len(old))==old
    patch_dol(raw,'rail-input-test')
