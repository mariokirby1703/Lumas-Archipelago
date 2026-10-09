"""Original capture reads, guarded overlays, and PPC thunk control flow.

Native calls in the thunk interpreter are stubs: this is NOT a Dolphin GPU,
collision or allocator test. The original native instructions are checked too.
"""
from pathlib import Path
from dataclasses import replace
import struct
import pytest
from ..Items import ITEM_TABLE, WISP_ITEMS
from ..client.runtime import Runtime
from ..client.journal import Journal
from ..client.hooks import NativeHooks
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.capsule_refresh import HOOK, ORIGINAL, payload_words, installed, gecko_ini
from .test_pickup_integration import Overlay
from .test_runtime import IDENTITY, snapshot
from .test_memory import FakeBackend
from . import generate

ROOT=Path(__file__).parents[1]/'notes/items_wisps_20261009'
STAMPS=(('184948','184953'),('190119','190127'),('190432','190440'),('190513','190521'))
PAIRS=[(ROOT/f'mem1(20261009-{a}).raw',ROOT/f'mem2(20261009-{b}).raw') for a,b in STAMPS]


@pytest.mark.skipif(not all(a.exists() and b.exists() for a,b in PAIRS),reason='private captures absent')
@pytest.mark.parametrize('index',range(4))
def test_new_original_counter_and_cached_capsule_evidence(index):
    m=SonicMemory(Overlay(PAIRS[index]));s=NativeHooks().snapshot(m)
    stage=s.evidence['native_data']['stage_objects'][0]
    assert s.scene=='gameplay' and stage['lives']==5
    assert m.read_u32(s.world_lives_address)==5
    assert m.read_u32(s.rings_address)==m.read_u32(s.ring_mirror_address)==(39,0,0,23)[index]
    assert stage['wisp_permissions']==(0,0x10,0x12,0x12)[index]
    assert s.actual_mission==('stg130' if index==0 else 'stg110')
    if index:
        c=next(c for c in stage['capsules'] if c['object_id']==23 and c['instance']==0)
        assert c['native_colour']==1 and not c['opened']
        assert c['actor']==(0x90B58400 if index<3 else 0x90CA9DA0)
        assert c['model_mode']==(0 if index<3 else 1)
        assert m.read_u32(c['actor']+0xa0)==(0x800D562C if index<3 else 0x800D629C)


class Guard:
    def check_stats(self,s):
        if s.scene!='gameplay' or s.death_state!='alive' or s.stable_polls<3:
            raise MemoryUnavailable('unsafe actor')
        return [s.stage_epoch,s.rings_address,s.lives_address]
class Hooks:
    def require(self,name):pass


def runtime_fixture(journal):
    r=Runtime(generate().worlds[1].fill_slot_data(),journal,Guard(),Hooks())
    r.snapshot=snapshot(stage_epoch='act1',rings_address=0x90001000,
                        ring_mirror_address=0x90001004,lives_address=0x90001008,
                        world_lives_address=0x9000100c)
    b=FakeBackend();m=SonicMemory(b,lambda *args:'verified fixture')
    tick=[0.];r.clock=lambda:tick[0]
    return r,b,m,tick


def settle(r,m,items,tick):
    start=tick[0];tick[0]=start+.6;r.apply_effects(m,items)
    tick[0]=start+2.1;r.apply_effects(m,items)


def test_repeated_lives_results_deferral_restart_uncertain_and_next_act(tmp_path):
    items=[ITEM_TABLE[n] for n in ('1-Up','1-Up','Rings (+10)','Ring Loss Trap')]
    with Journal(tmp_path,IDENTITY) as j:
        r,b,m,tick=runtime_fixture(j);j.record_history(items)
        r.snapshot=replace(r.snapshot,scene='results')
        r.apply_effects(m,items)
        assert not b.writes and all(e['state']=='deferred' for e in j.data['effects'].values())
        assert all(e['wait_epoch']=='act1' for e in j.data['effects'].values())
    with Journal(tmp_path,IDENTITY) as j:
        r,b,m,tick=runtime_fixture(j)
        # Even a transient living state in the same results actor cannot deliver.
        r.apply_effects(m,items);assert not b.writes
        r.snapshot=replace(r.snapshot,stage_epoch='act2')
        r.apply_effects(m,items);settle(r,m,items,tick);settle(r,m,items,tick)
        assert m.read_u32(r.snapshot.lives_address)==2
        assert m.read_u32(r.snapshot.world_lives_address)==2
        assert all(e['state']=='confirmed' for e in j.data['effects'].values())
        assert m.read_u32(r.snapshot.rings_address)==0
        writes=len(b.writes);r.apply_effects(m,items);assert len(b.writes)==writes


def test_uncertain_earlier_receipt_does_not_freeze_family(tmp_path):
    items=[ITEM_TABLE['1-Up'],ITEM_TABLE['1-Up'],ITEM_TABLE['Rings (+25)']]
    with Journal(tmp_path,IDENTITY) as j:
        r,b,m,tick=runtime_fixture(j);j.record_history(items)
        j.prepare(0,items[0],['old actor'],4,5)
    with Journal(tmp_path,IDENTITY) as j:
        r,b,m,tick=runtime_fixture(j);r.apply_effects(m,items);settle(r,m,items,tick)
        assert j.data['effects']['0']['state']=='uncertain'
        assert j.data['effects']['1']['state']=='confirmed'
        assert j.data['effects']['2']['state']=='confirmed'
        assert m.read_u32(r.snapshot.lives_address)==1
        assert len(r.item_details())==3
        j.recover_skip(0);assert j.data['effects']['0']['state']=='skipped_by_operator'


@pytest.mark.parametrize('trap',[False,True])
def test_normal_gameplay_counter_changes_do_not_replay_observed_effect(tmp_path,trap):
    with Journal(tmp_path,IDENTITY) as j:
        r,b,m,tick=runtime_fixture(j)
        for a in (r.snapshot.rings_address,r.snapshot.ring_mirror_address):b.put(a,(39).to_bytes(4,'big'))
        items=[ITEM_TABLE['Ring Loss Trap' if trap else 'Rings (+10)']]
        j.record_history(items);r.apply_effects(m,items)
        tick[0]=.1;r.apply_effects(m,items) # exact target on a later observation
        # Subsequent ordinary pickup (trap) or damage (filler) is legitimate.
        for a in (r.snapshot.rings_address,r.snapshot.ring_mirror_address):b.put(a,(5 if trap else 0).to_bytes(4,'big'))
        tick[0]=.6;r.apply_effects(m,items);tick[0]=2.1;r.apply_effects(m,items)
        assert j.data['effects']['0']['state']=='confirmed'
        assert len(b.writes)==2


def test_fast_exit_is_uncertain_and_later_receipts_still_apply(tmp_path):
    with Journal(tmp_path,IDENTITY) as j:
        r,b,m,tick=runtime_fixture(j);items=[ITEM_TABLE['Rings (+10)']];j.record_history(items)
        r.apply_effects(m,items)
        r.snapshot=replace(r.snapshot,stage_epoch='next')
        items.append(ITEM_TABLE['Rings (+25)']);j.record_history(items)
        r.apply_effects(m,items);settle(r,m,items,tick)
        assert j.data['effects']['0']['state']=='uncertain'
        assert j.data['effects']['1']['state']=='confirmed'
        assert m.read_u32(r.snapshot.rings_address)==35


@pytest.mark.skipif(not PAIRS[1][0].exists(),reason='private capture absent')
def test_only_exact_gecko_thunk_can_pass_native_revision_hash():
    m=SonicMemory(Overlay(PAIRS[1]));m.verify_revision();assert not installed(m)
    target=0x80001800;words=payload_words();words[-1]=0x48000000 | ((HOOK+4-(target+len(words)*4-4))&0x3fffffc)
    m.backend.write_bytes(target,struct.pack('>'+'I'*len(words),*words))
    m.backend.write_bytes(HOOK,(0x48000000|((target-HOOK)&0x3fffffc)).to_bytes(4,'big'))
    assert installed(m);m.verify_revision()
    m.backend.write_bytes(target+20,b'\0'*4)
    with pytest.raises(MemoryUnavailable,match='unrecognized capsule thunk'):m.verify_revision()


def test_wisp_names_keep_numeric_ids_and_exported_gecko_is_packaged():
    assert 'Cyan Laser Wisp' in WISP_ITEMS and 'Yellow Drill Wisp' in WISP_ITEMS
    assert not any('Unlock' in n for n in ITEM_TABLE)
    from ..world_constants import BASE_ID
    assert ITEM_TABLE['Cyan Laser Wisp']==BASE_ID+8
    assert (Path(__file__).parents[1]/'data/SNCP8P_capsule_refresh.ini').read_text()==gecko_ini()


@pytest.mark.skipif(not all(a.exists() and b.exists() for a,b in PAIRS),reason='private captures absent')
def test_repeated_original_native_counter_writes_across_act_initialization(tmp_path):
    from ..client.state import WritePolicy
    # These captures lack the user's host seed journal. Attribution is explicit
    # fixture input; address resolution, PAL hashing and writer gates are real.
    class AttributedFixture(Guard):
        def check(self,s):return self.check_stats(s)
    with Journal(tmp_path,IDENTITY) as j:
        hooks=NativeHooks();guard=AttributedFixture()
        r=Runtime(generate().worlds[1].fill_slot_data(),j,guard,hooks)
        tick=[0.];r.clock=lambda:tick[0]
        m=SonicMemory(Overlay(PAIRS[1]));m.write_guard=WritePolicy(m,guard,hooks.snapshot)
        for _ in range(3):r.snapshot=hooks.snapshot(m)
        items=[ITEM_TABLE['1-Up']];j.record_history(items)
        r.apply_effects(m,items);settle(r,m,items,tick)
        items.append(ITEM_TABLE['1-Up']);j.record_history(items)
        r.apply_effects(m,items);settle(r,m,items,tick)
        assert m.read_u32(r.snapshot.lives_address)==m.read_u32(r.snapshot.world_lives_address)==7
        m=SonicMemory(Overlay(PAIRS[0]));m.write_guard=WritePolicy(m,guard,hooks.snapshot)
        for _ in range(3):r.snapshot=hooks.snapshot(m)
        for name,expected in [('Rings (+25)',64),('Rings (+50)',114),('Ring Loss Trap',0)]:
            items.append(ITEM_TABLE[name]);j.record_history(items)
            r.apply_effects(m,items);settle(r,m,items,tick)
            assert m.read_u32(r.snapshot.rings_address)==m.read_u32(r.snapshot.ring_mirror_address)==expected
        assert all(e['state']=='confirmed' for e in j.data['effects'].values())


def test_prewrite_counter_race_retries_without_losing_or_duplicating_item(tmp_path):
    with Journal(tmp_path,IDENTITY) as j:
        r,b,m,tick=runtime_fixture(j);items=[ITEM_TABLE['Rings (+10)']];j.record_history(items)
        original=j.prepare
        changed=[False]
        def prepare(*args):
            original(*args)
            if not changed[0]:
                changed[0]=True
                for a in (r.snapshot.rings_address,r.snapshot.ring_mirror_address):b.put(a,(3).to_bytes(4,'big'))
        j.prepare=prepare
        r.apply_effects(m,items)
        assert j.data['effects']['0']['state']=='deferred' and not b.writes
        r.apply_effects(m,items);assert not b.writes
        tick[0]=.3;r.apply_effects(m,items);settle(r,m,items,tick)
        assert j.data['effects']['0']['state']=='confirmed'
        assert m.read_u32(r.snapshot.rings_address)==13 and len(b.writes)==2



def test_guard_rejection_after_mutation_cannot_be_retried_as_unwritten(tmp_path):
    with Journal(tmp_path,IDENTITY) as j:
        r,b,m,tick=runtime_fixture(j);items=[ITEM_TABLE['Rings (+10)']];j.record_history(items)
        def policy(*args):
            if b.writes:raise MemoryUnavailable('WRITE_BLOCKED: actor exited')
            return 'actor'
        m.write_guard=policy
        r.apply_effects(m,items)
        assert j.data['effects']['0']['state']=='uncertain'
        assert 'after_write' in j.data['effects']['0']['reason']
        assert len(b.writes)==1
        m.write_guard=lambda *args:'new actor';tick[0]=5;r.apply_effects(m,items)
        assert len(b.writes)==1
