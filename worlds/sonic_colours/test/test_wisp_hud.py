import struct
import pytest
from ..client import wisp_hud as h,native_events as n,capsule_refresh,progression_hook
from ..client.native_dol import plan,Dol,patch_dol
from .test_native_events import Machine


def machine(monkeypatch,colour,mask,index=0):
    rows=h.planned_patches();hooks=plan()[3]
    m=Machine('death');m.kind='wisp_hud'
    monkeypatch.setitem(n.HOOKS,'wisp_hud',(h.HOOK,h.ORIGINAL))
    for address,old,new in rows:m.b.put(address,new)
    caphook=next(x for x in hooks if x['hook']==capsule_refresh.HOOK)
    cap=caphook['target']+capsule_refresh.data_offset(capsule_refresh.payload_words(
        compact_abi=True,epilogue_abi=True,cache_permissions=True))
    prog=next(x for x in hooks if x['hook']==progression_hook.HOOK)['target']+progression_hook.payload()[1]
    actor=0x900c0000;owner=0x900d0000;m.r[30]=actor
    m.put(actor,0x80764440);m.put(actor+0x1b0,colour);m.put(actor+0x1a8,0)
    m.put(actor+0x1b4,-1)
    m.put(cap,owner);m.put(cap+4,index);m.b.put(owner,bytes([index]))
    m.put(prog,owner+0x24+index*0x19608);m.put(prog+8,mask)
    m.events=[]
    def call(target):
        if target==0x8012154c:
            assert m.r[3]==m.r[1]+0x30 and m.r[4]==0xffffffff and m.r[5]==0
            m.put(m.r[3]+0x14,-1);m.put(m.r[3]+0x18,0)
        else:
            assert target==0x80112a94 and m.r[3]==actor
            assert m.get(m.r[4]+0x14)==0xffffffff and m.get(m.r[4]+0x18)==0
            m.events.append('native icon removal');m.put(actor+0x1b0,-1)
        # Native callees may use every word of their outgoing home area.
        m.b.put(m.r[1]+8,bytes(0x20))
    m.native_call=call;m.before=m.r[:]
    return m,cap,prog,actor


@pytest.mark.parametrize('colour',range(7))
@pytest.mark.parametrize('owned',[False,True])
@pytest.mark.parametrize('index',range(4))
def test_cached_icon_reconciles_even_with_all_inventory_slots_already_empty(monkeypatch,colour,owned,index):
    m,cap,prog,actor=machine(monkeypatch,colour,1<<colour if owned else 127^(1<<colour),index)
    m.run()
    assert bool(m.events) is not owned
    assert m.get(actor+0x1b0)==(colour if owned else 0xffffffff)
    assert m.r[1]==m.before[1] and m.r[13:]==m.before[13:]
    assert m.lr==0x80001234 and m.ctr==0x80005678 and m.cr==0x12345678
    assert m.f[14:]==m.before_f[14:]
    m.events.clear();m.run();assert not m.events


@pytest.mark.parametrize('failure',['empty','unknown','class','unbound','index','owner'])
def test_wrong_context_never_sends_a_native_ui_event(monkeypatch,failure):
    m,cap,prog,actor=machine(monkeypatch,0,0)
    if failure=='empty':m.put(actor+0x1b0,-1)
    elif failure=='unknown':m.put(actor+0x1b0,8)
    elif failure=='class':m.put(actor,0x8075aef8)
    elif failure=='unbound':m.put(cap,0)
    elif failure=='index':m.put(cap+4,1)
    else:m.put(prog,0x900e0000)
    m.run();assert not m.events


def test_queued_owned_wisp_is_never_cancelled(monkeypatch):
    m,cap,prog,actor=machine(monkeypatch,0,2)
    m.put(actor+0x1b4,1);m.run()
    assert not m.events and m.get(actor+0x1b4)==1


def test_padding_and_hook_match_original_pal_and_have_no_collisions(pal_dol_bytes):
    from ..tools.private_assets import reference_root
    from ..world_constants import load_data
    original=pal_dol_bytes;im=Dol(original)
    for address,old,new in h.planned_patches():assert im.read(address,len(old))==old
    refs=set()
    for index,offset,base,size in im.sections:
        for i in range(0,size-3,4):
            word=struct.unpack_from('>I',im.data,offset+i)[0];refs.add(word)
            if index<7 and word>>26 in (16,18):
                mask,sign=(0xfffc,0x8000) if word>>26==16 else (0x3fffffc,0x2000000)
                delta=word&mask
                if delta&sign:delta-=sign*2
                refs.add(delta if word&2 else base+i+delta)
    for site in load_data('wisp_hud_sites.json'):
        address=site['address']
        assert (address+12)%16==0
        assert im.read(address-4,16)==bytes.fromhex('4e800020')+bytes(12)
        assert im.read(address+12,4).hex()==site['after']
        assert not any(address+i in refs for i in range(12))
    patch_dol(original,bytes(32))
