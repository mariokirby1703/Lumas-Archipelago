"""PAL live defect regressions: native original results, map gates, settlement."""
from dataclasses import replace
from pathlib import Path
import pytest
from ..client.status import StatusReporter
from ..client.journal import Journal
from ..client.runtime import Runtime, inventory
from ..client.state import SaveGuard, WritePolicy
from ..client.hooks import NativeHooks
from ..client.memory import SonicMemory
from ..Items import ITEM_TABLE, WORLD_ITEMS
from ..Locations import LOCATION_TABLE
from ..world_constants import STAGES
from . import generate
from .test_native_originals import PAIRS
from .test_pickup_integration import Overlay
from .test_runtime import IDENTITY, snapshot
from .test_memory import FakeBackend


def test_status_flapping_does_not_delay_events():
    reporter=StatusReporter(); emitted=[]; observations=[]
    for i in range(500):
        now=i*.02
        message='bound seed/save resumed' if i%2 else 'waiting for stable scene'
        observations.append(i)  # Scanner remains independent of reporter.
        if reporter.ready(message,now): emitted.append(message)
    assert len(emitted)<=2 and len(observations)==500
    assert reporter.ready('wrong_game: incorrect disc',10)


@pytest.mark.skipif(not PAIRS, reason='private original captures absent')
def test_intro_clear_and_b_rank_immediate_before_save(tmp_path):
    data=generate({'rank_checks':'all'}).worlds[1].fill_slot_data()
    with Journal(tmp_path,IDENTITY) as journal:
        hooks=NativeHooks(journal);guard=SaveGuard(journal)
        runtime=Runtime(data,journal,guard,hooks)
        for stamp in ('200443','201102','202546'):
            pair=next(p for p in PAIRS if stamp in p[0].name)
            runtime.poll(SonicMemory(Overlay(pair)),[],False)
        expected={LOCATION_TABLE[f'Tropical Resort Act {act} - {kind}'].code
                  for act in (1,2) for kind in ('Clear','B Rank','C Rank')}
        assert expected<=set(journal.data['checks'])
        assert journal.data['save_identity'] is None
        assert runtime.snapshot.current_result['grade']==2
        before=len(journal.data['pickup_events'])
        runtime.poll(SonicMemory(Overlay(pair)),[],False)
        assert len(journal.data['pickup_events'])==before


@pytest.mark.skipif(not PAIRS, reason='private original captures absent')
def test_nonfinal_result_is_not_credited(tmp_path):
    data=generate({'rank_checks':'all'}).worlds[1].fill_slot_data()
    with Journal(tmp_path,IDENTITY) as journal:
        hooks=NativeHooks(journal);guard=SaveGuard(journal);runtime=Runtime(data,journal,guard,hooks)
        runtime.poll(SonicMemory(Overlay(PAIRS[0])),[],False)
        pair=next(p for p in PAIRS if '201102' in p[0].name)
        backend=Overlay(pair);memory=SonicMemory(backend)
        state=hooks.snapshot(memory)
        backend.write_bytes(state.current_result['ui']+0xdc,(6).to_bytes(4,'big'))
        runtime.poll(memory,[],False)
        assert not any(code in journal.data['checks'] for name,code in data['locations'].items()
                       if LOCATION_TABLE[name].kind in ('clear','rank'))
        assert not runtime.snapshot.current_result['final']


@pytest.mark.skipif(not PAIRS, reason='private original captures absent')
def test_all_world_items_grant_only_first_act_and_starting_act(tmp_path):
    data=generate({'wisp_unlocks':'vanilla'}).worlds[1].fill_slot_data()
    with Journal(tmp_path,IDENTITY) as journal:
        hooks=NativeHooks(journal);guard=SaveGuard(journal);runtime=Runtime(data,journal,guard,hooks)
        for stamp in ('200443','202546','205502'):
            pair=next(p for p in PAIRS if stamp in p[0].name)
            runtime.poll(SonicMemory(Overlay(pair)),[],False)
        memory=SonicMemory(Overlay(pair));memory.write_guard=WritePolicy(memory,guard,hooks.snapshot)
        for _ in range(3):runtime.poll(memory,[],False)
        for zone,item in enumerate(WORLD_ITEMS):
            flags=memory.resolve_flags_ptr()[-1]
            before={int(row['bank_A']):memory.read_progress_bit(flags,int(row['bank_A'])) for row in hooks.progress_rows}
            hooks.project_permissions(memory,runtime.snapshot,inventory([ITEM_TABLE[item]]),data)
            first=next(s for s in STAGES if s['zone_index']==zone and s['slot']==1)
            bit=int(next(r['bank_A'] for r in hooks.progress_rows if r['mission']==first['mission_id']))
            assert memory.read_progress_bit(flags,20+zone) and memory.read_progress_bit(flags,bit)
            changed={b for b,v in before.items() if memory.read_progress_bit(flags,b)!=v}
            # Game Land flags have their own inventory gate projection; no other story act reveal.
            assert {b for b in changed if b<90}<={bit}


def test_delayed_verification_fair_trap_and_counter_reversion(tmp_path):
    class Guard:
        def check_stats(self,s):return ['actor']
    class Hooks:
        def require(self,name):pass
    data=generate().worlds[1].fill_slot_data()
    with Journal(tmp_path,IDENTITY) as journal:
        runtime=Runtime(data,journal,Guard(),Hooks());tick=[0.];runtime.clock=lambda:tick[0]
        backend=FakeBackend();memory=SonicMemory(backend,lambda *args:'actor')
        runtime.snapshot=snapshot(rings_address=0x90001000,ring_mirror_address=0x90001004,lives_address=0x90001008)
        items=[ITEM_TABLE['Ring Loss Trap'],ITEM_TABLE['Rings (+25)']]
        runtime.apply_effects(memory,items)
        assert '0' not in journal.data['effects'] and journal.data['effects']['1']['state']=='verifying'
        assert memory.read_u32(0x90001000)==25 and memory.read_u32(0x90001004)==25
        tick[0]=.6;runtime.apply_effects(memory,items)
        # Simulate native overwrite, the bug immediate readback used to hide.
        backend.put(0x90001000,(0).to_bytes(4,'big'));backend.put(0x90001004,(0).to_bytes(4,'big'))
        tick[0]=2.1;runtime.apply_effects(memory,items)
        assert journal.data['effects']['1']['state']=='uncertain'
        writes=len(backend.writes);runtime.apply_effects(memory,items)
        assert len(backend.writes)==writes


ROOT=Path(__file__).parents[1]/'notes/live_fix_985960d9'
@pytest.mark.skipif(not ROOT.exists(),reason='new private captures absent')
def test_new_capture_pause_is_not_write_safe_and_missing_map_bit():
    from ..tools.read_dumps import DumpBackend
    for a,b in zip(sorted(ROOT.glob('mem1*.raw')),sorted(ROOT.glob('mem2*.raw'))):
        memory=SonicMemory(DumpBackend(a,b));state=NativeHooks().snapshot(memory)
        flags=memory.resolve_flags_ptr()[-1]
        assert memory.read_progress_bit(flags,21) and not memory.read_progress_bit(flags,37)
        if '172056' in a.name:
            assert state.scene=='paused' and state.pickup_verified
            assert state.death_state!='alive'
            assert state.active_rings['stg120']==frozenset({2})

@pytest.mark.skipif(not ROOT.exists(),reason='new private captures absent')
def test_supplied_sweet_mountain_first_waypoint_refresh(tmp_path):
    pair=(next(ROOT.glob('mem1*171812*')),next(ROOT.glob('mem2*171821*')))
    memory=SonicMemory(Overlay(pair));hooks=NativeHooks()
    state=hooks.snapshot(memory);access=state.evidence['native_data']['stage_objects'][0]['world_map_access']
    assert access['zone']==1 and access['first_act_status']==1
    # Native reader/writer test with an explicitly assumed bound fixture; actual
    # bootstrap attribution is tested separately using the full original intro.
    class BoundFixture:
        def check(self,state):return ('test-bound-save',state.session)
    memory.write_guard=WritePolicy(memory,BoundFixture(),hooks.snapshot)
    data=generate({'wisp_unlocks':'vanilla'}).worlds[1].fill_slot_data()
    hooks.project_permissions(memory,state,inventory([ITEM_TABLE['Sweet Mountain Access']]),data)
    assert memory.read_u32(access['status_address'])==2
    flags=memory.resolve_flags_ptr()[-1]
    assert memory.read_progress_bit(flags,37)
    assert not memory.read_progress_bit(flags,38)
    assert not memory.read_progress_bit(flags,39)

@pytest.mark.skipif(not PAIRS,reason='private original captures absent')
def test_game_land_lives_do_not_overwrite_story_life_stock():
    pair=next(p for p in PAIRS if '210538' in p[0].name)
    memory=SonicMemory(Overlay(pair));state=NativeHooks().snapshot(memory)
    stage=state.evidence['native_data']['stage_objects'][0]
    assert stage['lives']==3 and memory.read_u32(stage['world_lives_address'])==5
    assert state.world_lives_address is None
