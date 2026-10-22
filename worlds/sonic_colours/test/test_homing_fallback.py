import struct
import pytest
from ..client import homing_fallback as h,native_events as n,movement_gate as g
from ..client.native_dol import plan,Dol,patch_dol
from .test_native_events import Machine


def machine(monkeypatch,selected,permissions):
    rows=h.planned_patches();hooks=plan()[3]
    m=Machine('death');m.kind='homing_fallback'
    monkeypatch.setitem(n.HOOKS,m.kind,(h.HOOK,h.ORIGINAL))
    for a,old,new in rows:m.b.put(a,new)
    control=next(x for x in hooks if x['hook']==g.HOOK)['target']+g.payload(gecko=True)[2]
    context=0x900a0000;player=0x900b0000;owner=0x900c0000;machine=0x900d0000
    m.r[3]=selected&0xffffffff;m.r[29]=context
    for a,value in ((control,1),(control+4,permissions),(context+0x28,player),
                    (player,g.PLAYER_VTABLE),(player+0x70,owner),(owner+8,machine),
                    (machine,g.STATE_MACHINE_VTABLE),(machine+0x28,player)):
        m.put(a,value)
    m.before=m.r[:]
    return m,control,player,machine


@pytest.mark.parametrize('mask',[0,1,2,3,4,5,7,127,256])
@pytest.mark.parametrize('selected',[-1,8,9,10,13,39])
def test_only_locked_homing_selection_falls_back_to_native_eligibility(monkeypatch,mask,selected):
    m,control,player,owner=machine(monkeypatch,selected,mask)
    m.run()
    expected=-1 if selected==13 and not mask&4 else selected
    assert m.r[3]==expected&0xffffffff
    assert m.r[:3]==m.before[:3] and m.r[4:]==m.before[4:]
    assert m.lr==0x80001234 and m.ctr==0x80005678 and not m.calls
    # No state request/availability flag is written: the original helper must
    # still pass 800919CC and 8020D1C0 before it can request a Double Jump.
    assert all(m.before[1]-0x20<=a<m.before[1] for a,data in m.b.writes)


@pytest.mark.parametrize('bad',['unarmed','player','machine','backref'])
def test_wrong_native_context_is_untouched(monkeypatch,bad):
    m,control,player,owner=machine(monkeypatch,13,1)
    if bad=='unarmed':m.put(control,0)
    elif bad=='player':m.put(player,0)
    elif bad=='machine':m.put(owner,0)
    else:m.put(owner+0x28,player+4)
    m.run();assert m.r[3]==13


def test_original_helper_and_audited_tail_call_padding():
    from ..tools.private_assets import reference_root
    from ..world_constants import load_data
    original=(reference_root()/'memdumps_and_more/main.dol').read_bytes();im=Dol(original)
    assert im.read(h.HOOK,4)==struct.pack('>I',h.ORIGINAL)
    # The original selector result is followed by the native fallback branch;
    # the fallback still queries its usual availability instead of forcing 8.
    assert im.read(0x800977d8,4)==bytes.fromhex('41820014')
    assert im.read(0x80097814,4)==bytes.fromhex('481759ad')
    refs=set()
    for index,offset,base,size in im.sections:
        for i in range(0,size-3,4):
            word=struct.unpack_from('>I',im.data,offset+i)[0];refs.add(word)
            if index<7 and word>>26 in (16,18):
                mask,sign=(0xfffc,0x8000) if word>>26==16 else (0x3fffffc,0x2000000)
                delta=word&mask
                if delta&sign:delta-=sign*2
                refs.add(delta if word&2 else base+i+delta)
    for site in load_data('homing_fallback_sites.json'):
        a=site['address'];before=int(site['before'],16)
        assert before>>26==18 and not before&1 and (a+12)%16==0
        assert im.read(a-4,16)==struct.pack('>I',before)+bytes(12)
        assert im.read(a+12,4).hex()==site['after']
        assert not any(a+i in refs for i in range(12))
    patch_dol(original,'test-homing-fallback')
