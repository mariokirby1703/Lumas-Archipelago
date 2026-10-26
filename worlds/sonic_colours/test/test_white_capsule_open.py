import struct
import pytest
from ..client import white_capsule_open as w,native_events as n,capsule_refresh
from ..client.native_dol import plan,Dol,patch_dol,branch
from .test_native_events import Machine


def machine(monkeypatch,permission,index=0):
    rows=w.planned_patches();hooks=plan()[3]
    m=Machine('death');m.kind='white_capsule_open'
    monkeypatch.setitem(n.HOOKS,m.kind,(w.HOOK,w.ORIGINAL))
    for a,o,new in rows:m.b.put(a,new)
    cap=next(h for h in hooks if h['hook']==capsule_refresh.HOOK)['target']+capsule_refresh.data_offset(capsule_refresh.payload_words(compact_abi=True,epilogue_abi=True,cache_permissions=True))
    actor=0x900c0000;owner=0x900d0000;m.r[28]=actor;m.r[3]=0
    m.put(actor+0x114,-1);m.put(cap,owner);m.put(cap+4,index);m.put(cap+8,permission);m.b.put(owner,bytes([index]))
    m.before=m.r[:]
    return m,cap,actor


@pytest.mark.parametrize('permission',range(4))
@pytest.mark.parametrize('index',range(4))
def test_open_requires_white_permission_not_random_capsules(monkeypatch,permission,index):
    m,cap,actor=machine(monkeypatch,permission,index);m.run()
    assert m.r[3]==int(not permission&1)
    assert m.r[1]==m.before[1] and m.r[4]==m.before[4] and m.r[13:]==m.before[13:]
    assert m.lr==0x80001234 and m.ctr==0x80005678 and m.f==m.before_f
    assert not m.calls and not m.b.writes


@pytest.mark.parametrize('failure',['unarmed','different_slot','invalid_slot'])
def test_first_frame_and_profile_replacement_fail_closed(monkeypatch,failure):
    m,cap,actor=machine(monkeypatch,3)
    if failure=='unarmed':m.put(cap,0)
    elif failure=='different_slot':m.put(cap+4,1)
    else:m.put(cap+4,4);m.b.put(0x900d0000,bytes([4]))
    m.run();assert m.r[3]==1


@pytest.mark.parametrize('kind',['multi','eggmask','colour','rejected'])
def test_other_capsules_and_existing_native_rejections_unchanged(monkeypatch,kind):
    m,cap,actor=machine(monkeypatch,0)
    if kind=='multi':m.b.put(actor+0x148,b'\1')
    elif kind=='eggmask':m.b.put(actor+0x14a,b'\1')
    elif kind=='colour':m.put(actor+0x114,1)
    else:m.r[3]=2
    m.run();assert m.r[3]==(2 if kind=='rejected' else 0)


def test_unlock_allows_same_capsule_without_reload(monkeypatch):
    m,cap,actor=machine(monkeypatch,0);m.run();assert m.r[3]==1
    m.put(cap+8,1);m.r[3]=0;m.run();assert m.r[3]==0


def test_original_callsites_and_padding():
    from ..tools.private_assets import reference_root
    from ..world_constants import load_data
    raw=(reference_root()/'memdumps_and_more/main.dol').read_bytes();im=Dol(raw)
    for a,old,new in w.planned_patches():assert im.read(a,len(old))==old
    assert im.read(w.HOOK,4)==struct.pack('>I',w.ORIGINAL)
    refs=set()
    for idx,off,base,size in im.sections:
        for i in range(0,size-3,4):
            word=struct.unpack_from('>I',im.data,off+i)[0];refs.add(word)
            if idx<7 and word>>26 in (16,18):
                mask,sign=(0xfffc,0x8000) if word>>26==16 else (0x3fffffc,0x2000000)
                delta=word&mask
                if delta&sign:delta-=2*sign
                refs.add(delta if word&2 else base+i+delta)
    for s in load_data('white_capsule_open_sites.json'):
        a=s['address'];assert im.read(a,s['size']).hex()==s['original']
        before=int(s['before'],16)
        assert im.read(s['anchor'],4)==struct.pack('>I',before)
        assert before==0x4e800020 or before>>26==18 and not before&1
        assert im.read(s['end'],4).hex()==s['after']
        assert not any(a+i in refs for i in range(s['size']))
    patch_dol(raw,bytes(32))
