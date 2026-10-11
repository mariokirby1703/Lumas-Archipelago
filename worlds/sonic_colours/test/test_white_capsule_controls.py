import struct
from pathlib import Path
from dataclasses import replace
import pytest
from ..client import capsule_refresh
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.hooks import NativeHooks
from ..client.state import WritePolicy
from ..client.native_read import read_stage_objects
from ..client.runtime import inventory
from ..client.progression_hook import configure as configure_progression
from ..Items import ITEM_TABLE, WISP_ITEMS, WORLD_ITEMS
from ..world_constants import BASE_ID
from ..tools.read_dumps import DumpBackend
from .test_native_originals import PAIRS
from .test_pickup_integration import Overlay

from .test_overhaul import install_progression
from .test_runtime import snapshot
from .test_memory import FakeBackend
from . import generate

ROOT=Path(__file__).parents[1]/'notes'
BEFORE=(ROOT/'mem1(20261010-025156).raw',ROOT/'mem2(20261010-025205).raw')
AFTER=(ROOT/'mem1(20261010-025226).raw',ROOT/'mem2(20261010-025235).raw')


@pytest.mark.skipif(not all(p.exists() for p in BEFORE+AFTER),reason='original White captures absent')
def test_original_white_transition_is_opening_not_gauge_increase():
    rows=[read_stage_objects(SonicMemory(DumpBackend(*pair)))[0] for pair in (BEFORE,AFTER)]
    assert all(r['mission']=='stg110' for r in rows)
    instances=[{c['instance']:c for c in r['capsules'] if c['object_id']==164} for r in rows]
    assert set(instances[0])==set(instances[1])=={0,1}
    first,last=instances[0][1],instances[1][1]
    assert first['actor']==last['actor']==0x90b59840
    assert first['native_colour']==last['native_colour']==-1
    assert not first['opened'] and last['opened']
    assert first['model_mode']==last['model_mode']==1
    assert first['model_state']==1 and last['model_state']==5
    assert not instances[0][0]['opened'] and not instances[1][0]['opened']
    assert all(r['player']['boost']==0 and r['player']['boost_max']==100 for r in rows)


def install(b,target=0x80002000):
    hook=capsule_refresh.HOOK;words=capsule_refresh.payload_words()
    words[-1]=0x48000000 | ((hook+4-(target+len(words)*4-4))&0x3fffffc)
    b.write_bytes(target,struct.pack('>'+'I'*len(words),*words))
    b.write_bytes(hook,(0x48000000 | ((target-hook)&0x3fffffc)).to_bytes(4,'big'))
    return target+capsule_refresh.data_offset(words)


def test_previous_white_thunk_retains_exact_guarded_ownership_data():
    from ..world_constants import load_data
    b=FakeBackend();m=SonicMemory(b);target=0x80002000
    words=load_data('capsule_white_previous.json')
    offset=capsule_refresh.data_offset(words)
    words[-1]=0x48000000 | ((capsule_refresh.HOOK+4-(target+len(words)*4-4))&0x3fffffc)
    b.write_bytes(target,struct.pack('>'+'I'*len(words),*words))
    b.write_bytes(capsule_refresh.HOOK,(0x48000000 | ((target-capsule_refresh.HOOK)&0x3fffffc)).to_bytes(4,'big'))
    b.write_bytes(target+offset,struct.pack('>3I',0x90001000,2,1))
    result=capsule_refresh.inspect_installed(m)
    assert result['variant']=='previous_white_collision_refresh'
    assert capsule_refresh.installed_data(m)==target+offset
    b.write_bytes(target+offset+8,(2).to_bytes(4,'big'))
    with pytest.raises(MemoryUnavailable):capsule_refresh.inspect_installed(m)


@pytest.mark.skipif(not PAIRS,reason='original PAL RAM absent')
def test_white_control_guard_exact_fields_and_new_permissions():
    b=Overlay(PAIRS[0]);m=SonicMemory(b);address=install(b)
    class Attributed:
        def check(self,s):return 'fixture bound'
        def check_stats(self,s):return 'fixture attributed live actor'
    h=NativeHooks();m.write_guard=WritePolicy(m,Attributed(),h.snapshot)
    snap=h.snapshot(m);slot=generate({'boost_lock':True}).worlds[1].fill_slot_data()
    result=capsule_refresh.configure(m,snap,inventory([]),slot)
    assert result['available'] and not result['white_allowed']
    assert m.read_u32(address+8)==0
    m.verify_revision()
    result=capsule_refresh.configure(m,snap,inventory([ITEM_TABLE['White Boost Wisp']]),slot)
    assert result['white_allowed'] and m.read_u32(address+8)==1
    with pytest.raises(MemoryUnavailable):m.write_u32(address+12,0,expected=0,operation='capsule_controls')
    b.write_bytes(address+8,(4).to_bytes(4,'big'))
    with pytest.raises(MemoryUnavailable,match='unknown_revision'):m.verify_revision()


@pytest.mark.skipif(not PAIRS,reason='original PAL RAM absent')
def test_native_terminal_velocity_projection_requires_only_eight_wisps():
    b=Overlay(PAIRS[0]);m=SonicMemory(b);address=install_progression(b)
    h=NativeHooks();snap=h.snapshot(m);slot=generate().worlds[1].fill_slot_data()
    # This test supplies an attributed fixture to exercise the native writer;
    # it does not turn the original dump into live save-binding evidence.
    snap=replace(snap,save_identity='fixture')
    class Attributed:
        def check(self,s):return 'fixture bound'
        def check_stats(self,s):return 'fixture bound stats'
    m.write_guard=WritePolicy(m,Attributed(),h.snapshot)
    assert len(WORLD_ITEMS)==6 and BASE_ID+6 not in ITEM_TABLE.values()
    for count in (7,8):
        owned=inventory([ITEM_TABLE[w] for w in WISP_ITEMS[:count]])
        configure_progression(m,snap,owned,slot)
        assert bool(m.read_u32(address+4)&(1<<26))==(count==8)
        h.project_permissions(m,snap,owned,slot)
        flags=m.resolve_flags_ptr()[-1]
        assert m.read_progress_bit(flags,26)==(count==8)
        assert m.read_progress_bit(flags,72)==(count==8)



