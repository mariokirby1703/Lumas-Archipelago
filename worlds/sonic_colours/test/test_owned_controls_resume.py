from dataclasses import replace
from types import SimpleNamespace
import pytest
from ..client.state import SaveGuard, Snapshot, WritePolicy
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.runtime import inventory
from ..client.hooks import NativeHooks
from ..client import progression_hook, capsule_refresh
from ..Items import ITEM_TABLE
from .test_memory import FakeBackend
from . import generate


def setup():
    journal=SimpleNamespace(data={'save_identity':'bound','native_monotonic_clears':['stg110','stg130','stg140']},
                            save=lambda:None,identity={'seed':'test','slot':1})
    chain=(0x90001000,0x90002000,0,0x90002008,0x90002024)
    snap=Snapshot('reopened','bound',1,'gameplay','stg120',stable_polls=3,
        persisted_clears=frozenset(['stg110','stg130']),save_identity_verified=True,
        scene_verified=True,progress_verified=True,death_state='alive',
        pickup_verified=True,stage_epoch='new-stage',rings_address=0x90005000,lives_address=0x90005004,
        evidence={'chain':chain,'native_data':{'stage_objects':[{'stage':0x90006000,'actor_state':0x90007000}]}})
    guard=SaveGuard(journal);guard.session=snap.session;guard.observe(snap)
    backend=FakeBackend();memory=SonicMemory(backend)
    memory.resolve_flags_ptr=lambda **kw:chain
    memory.verify_for_write=lambda operation:None
    memory.write_guard=WritePolicy(memory,guard,lambda mem:snap)
    return journal,guard,snap,memory,backend


def test_progress_difference_keeps_checks_and_items_enabled():
    journal,guard,snap,memory,backend=setup()
    before=dict(journal.data)
    assert guard.check_owned_controls(snap)
    assert guard.armed and guard.can_send(snap) and guard.can_record_pickups(snap)
    guard.check(snap);guard.check_stats(snap)
    assert journal.data==before


@pytest.mark.parametrize('change',[
    {'save_identity':'other'}, {'save_identity':None}, {'save_identity_verified':False},
    {'scene_verified':False}, {'progress_verified':False}, {'stable_polls':0},
    {'scene':'title'}, {'death_state':'dead'},
])
def test_recovery_requires_verified_same_save_and_safe_scene(change):
    journal,guard,snap,memory,backend=setup()
    with pytest.raises(MemoryUnavailable):guard.check_owned_controls(replace(snap,**change))


def test_same_session_progress_difference_does_not_disarm():
    journal,guard,snap,memory,backend=setup()
    guard.observe(replace(snap,persisted_clears=frozenset(journal.data['native_monotonic_clears'])))
    assert guard.armed
    guard.observe(snap)
    assert guard.armed
    guard.check(snap)


def test_actual_native_wisp_and_capsule_controls_republish_without_save_writes(monkeypatch):
    journal,guard,snap,memory,backend=setup()
    base=0x90003000;cap=0x90004000
    backend.put(base,bytes(32));backend.put(cap,bytes(12))
    def story(mem):
        mem.story_permissions_installed=True
        return base
    monkeypatch.setattr(progression_hook,'installed_data',story)
    monkeypatch.setattr(capsule_refresh,'installed_data',lambda mem:cap)
    memory.capsule_hook_observation={'variant':'current_compact_white_collision_refresh'}
    slot=generate().worlds[1].fill_slot_data()
    owned=inventory([ITEM_TABLE['Cyan Laser Wisp'],ITEM_TABLE['White Boost Wisp']])
    progression_hook.configure(memory,snap,owned,slot,journal)
    capsule_refresh.configure(memory,snap,owned,slot)
    monkeypatch.setattr(capsule_refresh,'inspect_installed',lambda mem:{'installed':False})
    NativeHooks().project_live_permissions(memory,snap,owned,slot)
    assert memory.read_u32(base)==snap.evidence['chain'][-1]
    from ..world_constants import NATIVE_COLOURS
    expected=1<<NATIVE_COLOURS.index('Cyan Laser')
    assert memory.read_u32(base+8)==expected
    assert memory.read_u32(cap+8)&1
    assert memory.read_u8(0x90006061)==expected
    assert memory.read_u8(0x90007090)==expected
    assert journal.data['native_monotonic_clears']==['stg110','stg130','stg140']
    assert guard.armed
    assert all(not (0x90002000<=a<0x90003000) for a,data in backend.writes)
    guard.check_stats(snap)


@pytest.mark.parametrize('scene',['world_map','global_map','gameplay'])
def test_reopen_after_unsaved_boss_clear_resumes_checks_and_permissions(scene):
    journal,guard,snap,memory,backend=setup()
    journal.data['native_monotonic_clears']=['stg110','stg130','stg120','stg140','stg150','stg160','stg190']
    journal.data['checks']=[847001192]
    journal.data['receipts']=[ITEM_TABLE['Cyan Laser Wisp']]
    journal.data['effects']={'0':{'state':'confirmed'}}
    original={key:journal.data[key] for key in ('checks','receipts','effects','native_monotonic_clears')}
    actual=frozenset(journal.data['native_monotonic_clears'])-{'stg190'}
    snap=replace(snap,session='new-emulation',scene=scene,persisted_clears=actual)
    guard.observe(snap)
    assert guard.armed and guard.can_send(snap)
    guard.check(snap)
    # Ordinary polls and new clears must not reintroduce the blockade.
    guard.observe(snap);assert guard.armed and guard.can_send(snap)
    guard.observe(replace(snap,persisted_clears=actual|{'stg210'}))
    assert guard.armed
    assert 'stg190' in journal.data['native_monotonic_clears']
    for key in ('checks','receipts','effects'):assert journal.data[key]==original[key]
    # A later RAM/save difference does not interrupt synchronization either.
    guard.observe(snap)
    assert guard.armed and guard.can_send(snap)


def test_missing_boss_cleared_again_finishes_resume_reconciliation():
    journal,guard,snap,memory,backend=setup()
    snap=replace(snap,session='new-emulation')
    guard.observe(snap);assert guard.armed
    complete=replace(snap,persisted_clears=frozenset(journal.data['native_monotonic_clears']))
    guard.observe(complete)
    assert guard.armed
    guard.observe(snap)
    assert guard.armed


def test_resume_never_credits_missing_boss_or_opens_its_successor():
    from ..world_progression import available_story_stages
    journal,guard,snap,memory,backend=setup()
    snap=replace(snap,session='new-emulation')
    guard.observe(snap)
    assert guard.armed
    assert 'stg140' not in snap.persisted_clears
    stages=available_story_stages(0,set(snap.persisted_clears),0)
    assert 'stg140' not in stages


@pytest.mark.parametrize('mode',[0,1])
def test_real_permission_projection_reopens_boss_after_cutscene_shutdown(monkeypatch,mode):
    journal,guard,snap,memory,backend=setup()
    from ..world_constants import load_data
    acts={'stg110','stg130','stg120','stg140','stg150','stg160'}
    journal.data['native_monotonic_clears']=sorted(acts|{'stg190'})
    node=0x90008000;backend.put(node,(1).to_bytes(4,'big'))
    row={'world_map_access':{'zone':0,'nodes':[{'slot':7,'status':1,'address':node}]}}
    snap=replace(snap,session='new-emulation',scene='world_map',actual_mission=None,
                 persisted_clears=frozenset(acts),
                 evidence={'chain':snap.evidence['chain'],'native_data':{'stage_objects':[row]}})
    guard.observe(snap)
    memory.write_guard=WritePolicy(memory,guard,lambda mem:snap)
    hooks=NativeHooks()
    monkeypatch.setattr(hooks,'project_live_permissions',lambda *a:None)
    slot=generate({'world_progression':mode}).worlds[1].fill_slot_data()
    hooks.project_permissions(memory,snap,inventory([]),slot)
    assert memory.read_u32(node)==2
    boss_bit=int(next(r['bank_A'] for r in load_data('progress_bits.json') if r['mission']=='stg190'))
    flags=snap.evidence['chain'][-1]
    assert memory.read_u32(flags+0x10+boss_bit//32*4)&(1<<(boss_bit%32))
    assert guard.can_send(snap)
    assert 'stg190' not in snap.persisted_clears
