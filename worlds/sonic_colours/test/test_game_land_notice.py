from dataclasses import replace
import pytest
from ..client.game_land_notice import prepare,apply
from ..client.native_read import APPLICATION_GLOBAL
from ..client.memory import MemoryUnavailable
from ..client.state import WritePolicy
from ..world_constants import game_land_gates
from .test_physical_ring_collection import setup


def fixture(tmp_path):
    j,m,b,s,g,chain,_=setup(tmp_path)
    app,doc,module,owner=0x90050000,0x90051000,0x90052000,0x90053000
    for a,v in ((APPLICATION_GLOBAL,app),(app+4,doc),(doc+0x1c,module),
                (module+0x38,owner),(owner,0x8076AC7C),(owner+0x1c,module),
                (owner+0x64,owner+0x70),(owner+0x68,0),(owner+0x6c,0x80000005)):
        b.put(a,v.to_bytes(4,'big'))
    return j,m,b,s,g,chain,owner


def test_actual_queue_layout_and_flag_notification_without_fake_physical_rings(tmp_path):
    j,m,b,s,g,chain,owner=fixture(tmp_path)
    with j:
        state=prepare(m,s,{'red_rings':4},{'game_land_gates':game_land_gates(113)},j)
        assert state['pending']==['2-1']
        before_physical=m.read_u32(chain[-1]+0x10+40)
        result=apply(m,s,g,j)
        assert m.read_u32(owner+0x68)==1 and m.read_u32(owner+0x70)==2
        assert m.read_u32(owner+0x74)==0
        assert m.read_u32(chain[-1]+0x10)&(1<<11)
        assert m.read_u32(chain[-1]+0x10+40)==before_physical
        assert not result['visual_verified']
        n=len(b.writes);apply(m,s,g,j);assert len(b.writes)==n


@pytest.mark.parametrize('field,value',[(0,0),(0x1c,0),(0x64,0),(0x6c,0),(0x68,6)])
def test_rejects_changed_native_owner_and_overflow(tmp_path,field,value):
    j,m,b,s,g,chain,owner=fixture(tmp_path)
    with j:
        prepare(m,s,{'red_rings':4},{'game_land_gates':game_land_gates(113)},j)
        b.put(owner+field,value.to_bytes(4,'big'))
        with pytest.raises(MemoryUnavailable):apply(m,s,g,j)
        assert not b.writes


def test_full_queue_and_menu_defer_durably(tmp_path):
    j,m,b,s,g,chain,owner=fixture(tmp_path)
    with j:
        state=prepare(m,s,{'red_rings':4},{'game_land_gates':game_land_gates(113)},j)
        b.put(owner+0x68,(5).to_bytes(4,'big'))
        with pytest.raises(MemoryUnavailable,match='full'):apply(m,s,g,j)
        with pytest.raises(MemoryUnavailable,match='deferred'):
            apply(m,replace(s,scene='world_map'),g,j)
        assert state['pending']==['2-1'] and not b.writes


def test_uncertain_native_publish_does_not_automatically_duplicate_animation(tmp_path):
    j,m,b,s,g,chain,owner=fixture(tmp_path)
    with j:
        prepare(m,s,{'red_rings':4},{'game_land_gates':game_land_gates(113)},j)
        original_write=b.write_bytes
        def corrupt_count(address,data):
            original_write(address,b'\xff'*4 if address==owner+0x68 else data)
        b.write_bytes=corrupt_count
        with pytest.raises(MemoryUnavailable):apply(m,s,g,j)
        assert j.data['game_land_notice']['state']=='uncertain'
        n=len(b.writes);apply(m,s,g,j);assert len(b.writes)==n


def test_inactive_slot_failure_remains_retryable_and_records_actual_error(tmp_path):
    j,m,b,s,g,chain,owner=fixture(tmp_path)
    with j:
        prepare(m,s,{'red_rings':4},{'game_land_gates':game_land_gates(113)},j)
        b.corrupt=True
        with pytest.raises(MemoryUnavailable):apply(m,s,g,j)
        state=j.data['game_land_notice']
        assert state['state']=='idle' and not state['publish_attempted']
        assert 'readback_mismatch' in state['last_error']
        b.corrupt=False
        apply(m,s,g,j)
        assert m.read_u32(owner+0x68)==1


def test_legacy_cosmetic_uncertainty_recovers_once_only_when_inactive(tmp_path):
    j,m,b,s,g,chain,owner=fixture(tmp_path)
    with j:
        state=prepare(m,s,{'red_rings':4},{'game_land_gates':game_land_gates(113)},j)
        state['state']='uncertain'
        apply(m,s,g,j)
        assert state['legacy_retry_used'] and state['state']=='idle'
        assert m.read_u32(owner+0x68)==1
