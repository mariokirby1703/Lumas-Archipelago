import struct
import pytest
from ..client import random_wisp_spawns as w,native_events as n,capsule_refresh,progression_hook
from ..client.native_dol import plan,Dol,patch_dol,branch
from .test_native_events import Machine


def machine(monkeypatch,colour,mask,index=0,hook=None):
    rows=w.planned_patches();hooks=plan()[3];hook=hook or w.HOOKS[0]
    m=Machine('death');m.kind='random_wisp_spawn'
    monkeypatch.setitem(n.HOOKS,m.kind,(hook,branch(hook,w.SPAWN)|1))
    for a,o,new in rows:m.b.put(a,new)
    cap=next(h for h in hooks if h['hook']==capsule_refresh.HOOK)['target']+capsule_refresh.data_offset(capsule_refresh.payload_words(compact_abi=True,epilogue_abi=True,cache_permissions=True))
    prog=next(h for h in hooks if h['hook']==progression_hook.HOOK)['target']+progression_hook.payload()[1]
    args=0x900c0000;owner=0x900d0000;m.r[3]=m.stage;m.r[4]=args
    m.put(args+0x20,colour);m.put(cap,owner);m.put(cap+4,index);m.b.put(owner,bytes([index]))
    m.put(prog,owner+0x24+index*0x19608);m.put(prog+8,mask)
    m.put(w.SPAWN,0x4e800020);m.spawned=False;get=m.get
    def tracked(a):
        if a==w.SPAWN:m.spawned=True
        return get(a)
    m.get=tracked;m.before=m.r[:]
    return m,cap,prog


@pytest.mark.parametrize('colour',range(7))
@pytest.mark.parametrize('owned',[False,True])
@pytest.mark.parametrize('index',range(4))
def test_each_spawn_is_filtered_before_allocation(monkeypatch,colour,owned,index):
    m,cap,prog=machine(monkeypatch,colour,1<<colour if owned else 127^(1<<colour),index)
    m.run();assert m.spawned is owned
    assert m.r[1:5]==m.before[1:5] and m.r[13:]==m.before[13:]
    assert m.f==m.before_f and m.ctr==0x80005678
    assert m.lr==w.HOOKS[0]+4
    assert not m.b.writes and not m.calls


@pytest.mark.parametrize('hook',w.HOOKS)
def test_all_multi_capsule_outputs_keep_drill_but_suppress_laser(monkeypatch,hook):
    for colour,expected in ((0,True),(1,False)):
        m,cap,prog=machine(monkeypatch,colour,1,hook=hook)
        m.run();assert m.spawned is expected


@pytest.mark.parametrize('case',['inactive','wrong_index','wrong_owner','white','unknown'])
def test_policy_lifetime_and_unrelated_outputs(monkeypatch,case):
    m,cap,prog=machine(monkeypatch,1,0)
    expected=False
    if case=='inactive':m.put(cap,0);expected=True
    elif case=='wrong_index':m.put(cap+4,1)
    elif case=='wrong_owner':m.put(prog,0)
    elif case=='white':m.put(m.r[4]+0x20,-1);expected=True
    else:m.put(m.r[4]+0x20,8);expected=True
    m.run();assert m.spawned is expected


def test_ap_unlock_updates_next_spawn_without_scene_reload(monkeypatch):
    m,cap,prog=machine(monkeypatch,1,0);m.run();assert not m.spawned
    m.put(prog+8,2);m.run();assert m.spawned


def test_original_callsites_and_padding(pal_dol_bytes):
    from ..tools.private_assets import reference_root
    from ..world_constants import load_data
    raw=pal_dol_bytes;im=Dol(raw)
    for a,old,new in w.planned_patches():assert im.read(a,len(old))==old
    for hook in w.HOOKS:assert im.read(hook,4)==struct.pack('>I',branch(hook,w.SPAWN)|1)
    refs=set()
    for idx,off,base,size in im.sections:
        for i in range(0,size-3,4):
            word=struct.unpack_from('>I',im.data,off+i)[0];refs.add(word)
            if idx<7 and word>>26 in (16,18):
                mask,sign=(0xfffc,0x8000) if word>>26==16 else (0x3fffffc,0x2000000)
                delta=word&mask
                if delta&sign:delta-=2*sign
                refs.add(delta if word&2 else base+i+delta)
    for s in load_data('random_wisp_spawn_sites.json'):
        a=s['address'];assert im.read(a,s['size']).hex()==s['original']
        before=int(s['before'],16)
        assert im.read(s['anchor'],4)==struct.pack('>I',before)
        assert before==0x4e800020 or before>>26==18 and not before&1
        assert im.read(s['end'],4).hex()==s['after']
        assert not any(a+i in refs for i in range(s['size']))
    patch_dol(raw,bytes(32))
