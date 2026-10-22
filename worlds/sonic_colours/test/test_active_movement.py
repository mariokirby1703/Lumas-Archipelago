import struct
import pytest
from ..client import active_movement as a,native_events as n,movement_gate as g
from ..client.native_dol import plan,Dol,patch_dol
from .test_native_events import Machine


def machine(monkeypatch,kind,mask,water=False):
    rows=a.planned_patches();hooks=plan()[3]
    m=Machine('death');m.kind='active_'+kind
    hook,original,vt,permission,fallback=a.HOOKS[kind]
    monkeypatch.setitem(n.HOOKS,m.kind,(hook,original))
    for address,old,new in rows:m.b.put(address,new)
    state=0x900a0000;owner=0x900b0000;player=0x900c0000;holder=0x900d0000;stats=0x900e0000
    control=next(h for h in hooks if h['hook']==g.HOOK)['target']+g.payload(gecko=True)[2]
    current={'drift':38,'jump':8,'stomp':44}[kind]
    for address,value in ((state,vt),(owner,g.STATE_MACHINE_VTABLE),(owner+0x28,player),
                          (owner+0x1c,current),(owner+0x20,current),(player,g.PLAYER_VTABLE),
                          (player+0x70,holder),(holder+8,owner),(player+0x8c,stats),
                          (stats+0x10,0x800 if water else 0),(control,1),(control+4,mask)):
        m.put(address,value)
    m.r[3]=state;m.r[4]=owner;m.before=m.r[:]
    def call(target):
        assert target==0x80033878 and m.r[3]==owner and m.r[4]==fallback
        # Model the documented native transition rather than host state writes.
        m.put(owner+0x20,fallback)
    m.native_call=call
    return m,control,state,owner,player


@pytest.mark.parametrize('kind',['drift','jump','stomp'])
@pytest.mark.parametrize('mask',[0,1,4,64,128,256,511])
@pytest.mark.parametrize('water',[False,True])
def test_active_callbacks_enforce_independent_permissions(monkeypatch,kind,mask,water):
    m,control,state,owner,player=machine(monkeypatch,kind,mask,water)
    permission=256 if kind=='jump' and water else a.HOOKS[kind][3]
    allowed=bool(mask&permission);m.run()
    assert bool(m.calls) is not allowed
    assert m.lr==0x80001234 and m.r[9:]==m.before[9:]
    if allowed:
        size={'drift':0x30,'jump':0x20,'stomp':0x60}[kind]
        assert m.r[1]==m.before[1]-size and m.f==m.before_f
        assert m.r[3:5]==m.before[3:5]
    else:assert m.r[1]==m.before[1] and m.r[3]==1


@pytest.mark.parametrize('kind',['drift','jump','stomp'])
@pytest.mark.parametrize('case',['unarmed','other_state','other_machine','other_player','backref','pending_death','pending_script'])
def test_inactive_policy_and_unsafe_transitions_keep_original_callback(monkeypatch,kind,case):
    m,control,state,owner,player=machine(monkeypatch,kind,0)
    if case=='unarmed':m.put(control,0)
    elif case=='other_state':m.put(state,0)
    elif case=='other_machine':m.put(owner,0)
    elif case=='other_player':m.put(player,0)
    elif case=='backref':m.put(m.get(player+0x70)+8,owner+4)
    elif case=='pending_death':m.put(owner+0x20,24)
    else:m.put(owner+0x20,98)
    m.run();assert not m.calls


def test_callback_slots_original_bytes_and_full_patch_are_verified():
    from ..tools.private_assets import reference_root
    from ..world_constants import load_data
    raw=(reference_root()/'memdumps_and_more/main.dol').read_bytes();im=Dol(raw)
    for kind,(hook,original,vt,*_) in a.HOOKS.items():
        assert im.read(hook,4)==struct.pack('>I',original)
        assert im.read(vt+0x34,4)==struct.pack('>I',hook)
    for address,old,new in a.planned_patches():assert im.read(address,len(old))==old
    refs=set()
    for index,offset,base,size in im.sections:
        for i in range(0,size-3,4):
            word=struct.unpack_from('>I',im.data,offset+i)[0];refs.add(word)
            if index<7 and word>>26 in (16,18):
                mask,sign=(0xfffc,0x8000) if word>>26==16 else (0x3fffffc,0x2000000)
                delta=word&mask
                if delta&sign:delta-=sign*2
                refs.add(delta if word&2 else base+i+delta)
    for site in load_data('active_movement_sites.json'):
        start=site['anchor'];end=site['end'];before=int(site['before'],16)
        assert im.read(start,4)==struct.pack('>I',before)
        assert before==0x4e800020 or before>>26==18 and not before&1
        if before!=0x4e800020:
            delta=before&0x3fffffc
            if delta&0x2000000:delta-=0x4000000
            target=delta if before&2 else start+delta
            assert not start+4<=target<end
        assert all(w[0] in (0,0x60000000) for w in struct.iter_unpack('>I',im.read(start+4,end-start-4)))
        assert not any(site['address']+i in refs for i in range(site['size']))
    patched,_=patch_dol(raw,'active-movement-test');patched=Dol(patched)
    for site in load_data('active_movement_sites.json'):
        assert patched.read(site['anchor'],4)==im.read(site['anchor'],4)
