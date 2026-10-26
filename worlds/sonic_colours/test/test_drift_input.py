import struct
import pytest
from ..client import drift_input as d,native_events as n,movement_gate as g
from ..client.native_dol import plan,Dol,patch_dol
from .test_native_events import Machine


@pytest.mark.parametrize('hook',d.HOOKS)
@pytest.mark.parametrize('armed',[0,1,0x90001000])
@pytest.mark.parametrize('mask',[0,1,4,64,128,256,0x1fff])
@pytest.mark.parametrize('native_pressed',[0,1])
def test_selection_and_continuation_require_drift_permission(monkeypatch,hook,armed,mask,native_pressed):
    rows=d.planned_patches();hooks=plan()[3]
    m=Machine('death');m.kind='drift_input'
    monkeypatch.setitem(n.HOOKS,m.kind,(hook,d.ORIGINAL))
    for a,o,new in rows:m.b.put(a,new)
    control=next(h for h in hooks if h['hook']==g.HOOK)['target']+g.payload(gecko=True)[2]
    m.put(control,armed);m.put(control+4,mask);m.r[3]=native_pressed;m.before=m.r[:]
    for _ in range(3):
        m.r[3]=native_pressed;m.run()
        assert m.r[3]==(native_pressed if not armed or mask&128 else 0)
    assert m.r[1:3]==m.before[1:3] and m.r[4:12]==m.before[4:12] and m.r[13:]==m.before[13:]
    assert m.f==m.before_f and m.lr==0x80001234 and m.ctr==0x80005678
    assert not m.b.writes and not m.calls
    # A receipt updates the predicate immediately, without resetting the state.
    m.put(control+4,mask|128);m.r[3]=native_pressed;m.run()
    assert m.r[3]==native_pressed


def test_native_drift_branch_semantics_and_exact_padding():
    from ..tools.private_assets import reference_root
    from ..world_constants import load_data
    raw=(reference_root()/'memdumps_and_more/main.dol').read_bytes();im=Dol(raw)
    for a,old,new in d.planned_patches():assert im.read(a,len(old))==old
    assert im.read(0x80066f24,4)==bytes.fromhex('41820058')  # false skips drift selection
    assert im.read(0x8015058c,4)==bytes.fromhex('40820040')  # false follows Run exit
    assert im.read(0x801505bc,8)==bytes.fromhex('388000034bee32b9')
    refs=set()
    for idx,off,base,size in im.sections:
        for i in range(0,size-3,4):
            word=struct.unpack_from('>I',im.data,off+i)[0];refs.add(word)
            if idx<7 and word>>26 in (16,18):
                mask,sign=(0xfffc,0x8000) if word>>26==16 else (0x3fffffc,0x2000000)
                delta=word&mask
                if delta&sign:delta-=2*sign
                refs.add(delta if word&2 else base+i+delta)
    for site in load_data('drift_input_sites.json'):
        a=site['address'];before=int(site['before'],16)
        assert im.read(a-4,16)==struct.pack('>I',before)+bytes(12)
        assert before==0x4e800020 or before>>26==18 and not before&1
        assert im.read(a+12,4).hex()==site['after']
        assert not any(a+i in refs for i in range(12))
    patch_dol(raw,bytes(32))
