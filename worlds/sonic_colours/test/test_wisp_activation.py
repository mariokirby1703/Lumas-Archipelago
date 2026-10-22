import struct
import pytest
from ..client import wisp_activation as w,native_events as n,capsule_refresh,progression_hook
from ..client.native_dol import plan,Dol,patch_dol
from .test_native_events import Machine


def setup_machine(monkeypatch,colour,mask,index):
    rows=w.planned_patches();hooks=plan()[3]
    m=Machine('death');m.kind='wisp_activation'
    monkeypatch.setitem(n.HOOKS,m.kind,(w.HOOK,w.ORIGINAL))
    for a,o,new in rows:m.b.put(a,new)
    cap=next(h for h in hooks if h['hook']==capsule_refresh.HOOK)['target']+capsule_refresh.data_offset(capsule_refresh.payload_words(compact_abi=True,epilogue_abi=True,cache_permissions=True))
    prog=next(h for h in hooks if h['hook']==progression_hook.HOOK)['target']+progression_hook.payload()[1]
    model=0x900c0000;container=0x900d0000
    m.r[3]=model;m.put(model,0x80763a18);m.put(model+0x18,colour)
    m.put(cap,container);m.put(cap+4,index);m.b.put(container,bytes([index]))
    m.put(prog,container+0x24+index*0x19608);m.put(prog+8,mask)
    m.before=m.r[:]
    return m,cap,prog,model


@pytest.mark.parametrize('colour',range(7))
@pytest.mark.parametrize('owned',[False,True])
@pytest.mark.parametrize('index',range(4))
def test_native_held_query_denies_unowned_without_waiting_for_inventory_clear(monkeypatch,colour,owned,index):
    m,cap,prog,model=setup_machine(monkeypatch,colour,1<<colour if owned else 127^(1<<colour),index)
    for _ in range(3):
        m.r[3]=model;m.run()
        assert m.r[3]==(colour if owned else 0xffffffff)
        assert m.get(model+0x18)==colour
    assert not m.b.writes and not m.calls
    assert m.r[1]==m.before[1] and m.r[13:]==m.before[13:]
    assert m.lr==0x80001234 and m.ctr==0x80005678 and m.f==m.before_f


@pytest.mark.parametrize('failure',['inactive','index','owner','empty','unknown'])
def test_native_policy_lifetime_and_special_values(monkeypatch,failure):
    m,cap,prog,model=setup_machine(monkeypatch,1,0,0)
    expected=0xffffffff
    if failure=='inactive':m.put(cap,0);expected=1
    elif failure=='index':m.put(cap+4,2)
    elif failure=='owner':m.put(prog,0x900e0000)
    elif failure=='empty':m.put(model+0x18,-1)
    else:m.put(model+0x18,10);expected=10
    m.run();assert m.r[3]==expected
    assert not m.b.writes and not m.calls


def test_late_item_receipt_immediately_changes_native_query(monkeypatch):
    m,cap,prog,model=setup_machine(monkeypatch,1,0,0)
    m.run();assert m.r[3]==0xffffffff
    m.put(prog+8,2);m.r[3]=model;m.run();assert m.r[3]==1


def test_original_hook_and_padding_proof():
    from ..tools.private_assets import reference_root
    from ..world_constants import load_data
    raw=(reference_root()/'memdumps_and_more/main.dol').read_bytes();im=Dol(raw)
    for a,old,new in w.planned_patches():assert im.read(a,len(old))==old
    refs=set()
    for idx,off,base,size in im.sections:
        for i in range(0,size-3,4):
            word=struct.unpack_from('>I',im.data,off+i)[0];refs.add(word)
            if idx<7 and word>>26 in (16,18):
                mask,sign=(0xfffc,0x8000) if word>>26==16 else (0x3fffffc,0x2000000)
                delta=word&mask
                if delta&sign:delta-=2*sign
                refs.add(delta if word&2 else base+i+delta)
    for site in load_data('wisp_activation_sites.json'):
        a=site['address'];before=int(site['before'],16)
        assert im.read(a-4,16)==struct.pack('>I',before)+bytes(12)
        assert before==0x4e800020 or before>>26==18 and not before&1
        assert im.read(a+12,4).hex()==site['after']
        assert not any(a+i in refs for i in range(12))
    patch_dol(raw,bytes(32))
