"""New Game must send mandatory intro checks before the first vanilla save slot.

These tests preserve strict write blocking for selected-save bits while
allowing native scene-local results/pickups on an attributed seed intro.
"""
from dataclasses import replace
from types import SimpleNamespace
import pytest

from ..client import hooks as hooks_module
from ..client.hooks import NativeHooks
from ..client.binding import SaveBinding
from ..client.memory import MemoryUnavailable
from ..client.state import SaveGuard, Snapshot, PlaythroughState


class Journal:
    def __init__(self):
        self.identity = dict(seed='test-newgame', team=0, slot=1, revision='PAL')
        self.data = dict(save_identity=None, bootstrap=None, native_binding=None,
                         pickup_events=[], checks=[], native_monotonic_clears=[])
        self.data.pop('bootstrap')
        self.saved = 0
    def save(self): self.saved += 1


def stage(*, mission='stg110', rings=0, deaths=0, scene='gameplay'):
    return {'application':0x90001000,'context':0x90002000,'actor_state':0x90003000,
            'player_actor_id':7, 'mission':mission,'scene':scene,
            'clicked_slot':'0:1','death_count':deaths,'current_red_ring_mask':0,
            'lives_address':0x90005000,'ring_mirror_address':0x90005010,
            'world_lives_address':0x90005020,
            'player':dict(actor=0x90004000,mode=0,rings=rings,
                          rings_address=0x90004040,boost_address=0x90004048,
                          boost_max_address=0x90004054)}


class FakeMemory:
    def verify_revision(self): return 'PAL exact hash'
    def trace_save_chain(self):
        return {'chain':None,'status':'index_out_of_range',
                'first_failure':{'step':'selected_index','reason':'index_out_of_range'},
                'steps':[{'step':'selected_index','address':'0x9310DDA0',
                          'raw':'0xFF','reason':'index_out_of_range'}]}


def initialize(monkeypatch, player=None):
    journal=Journal()
    native=NativeHooks(journal)
    scene=player if player is not None else stage()
    monkeypatch.setattr(hooks_module, 'read_stage_objects', lambda mem,**kwargs: [scene])
    memory=FakeMemory()
    snapshots=[native.snapshot(memory) for _ in range(4)]
    guard=SaveGuard(journal)
    for snap in snapshots: guard.observe(snap)
    return journal,native,guard,snapshots


def test_unselected_intro_bootstraps_without_selecting_fake_save(monkeypatch):
    journal,native,guard,snaps=initialize(monkeypatch)
    assert [s.stable_polls for s in snaps]==[1,2,3,4]
    assert not snaps[1].new_game_verified and snaps[2].new_game_verified
    assert snaps[2].save_identity is None and not snaps[2].progress_verified
    assert journal.data['bootstrap']['intro_proof']=='native_unselected_intro_v1'
    assert native.binding.intro_session==snaps[2].session
    assert snaps[2].boost_address==0x90004048
    assert snaps[2].boost_max_address==0x90004054
    assert guard.state==PlaythroughState.MANDATORY_PROLOGUE
    assert guard.can_record_pickups(snaps[-1]) and guard.can_send(snaps[-1])
    assert guard.check_stats(snaps[-1])
    with pytest.raises(MemoryUnavailable,match='save_not_bound'):
        guard.check(snaps[-1])  # save bank writes never become valid


@pytest.mark.parametrize('bad',[
    dict(rings=5),dict(deaths=1),dict(mission='stg120'),dict(scene='world_map'),
])
def test_no_fabricated_intro_when_native_evidence_missing(monkeypatch,bad):
    journal,native,guard,snaps=initialize(monkeypatch,stage(**bad))
    assert not snaps[-1].new_game_verified
    assert 'bootstrap' not in journal.data
    assert not guard.can_send(snaps[-1])


def test_unselected_intro_can_bind_after_two_native_result_witnesses(monkeypatch):
    journal,native,guard,snaps=initialize(monkeypatch)
    epoch=journal.data['bootstrap']['epoch']
    session=snaps[-1].session
    for mission,score,grade in [('stg110',12300,2),('stg130',15500,1)]:
        journal.data['pickup_events'].append(dict(kind='result',mission=mission,
            score=score,grade=grade,session=session,playthrough_epoch=epoch,
            provenance='stage9C_native_UI_state7_grade124'))
    fake_saved={
        'chain':(0x9000,0x9001,1,0x9003,0x9004),
        'profile_hex':'test_profile_03',
        'rank_records':{'stg110':{'raw_rank':2,'score':12300,'time_raw':140},
                        'stg130':{'raw_rank':1,'score':15500,'time_raw':155}}
    }
    snap=replace(snaps[-1],scene='global_map',actual_mission=None,
        pickup_verified=False,progress_verified=True,scene_verified=True,
        persisted_clears=frozenset(('stg110','stg130')))
    bound=native.binding.attribute(snap,fake_saved)
    assert bound.save_identity==epoch and bound.save_identity_verified
    guard.observe(bound)
    assert journal.data['save_identity']==epoch
    assert guard.can_send(bound)
    assert journal.data['native_binding']['selected_index']==1


def test_old_save_cannot_bind_without_matching_live_results(monkeypatch):
    journal,native,guard,snaps=initialize(monkeypatch)
    saved={'chain':(0x9000,0x9001,1,0x9003,0x9004),'profile_hex':'old',
           'rank_records':{'stg110':{'raw_rank':2,'score':12300,'time_raw':140},
                           'stg130':{'raw_rank':1,'score':15500,'time_raw':155}}}
    snap=replace(snaps[-1],scene='global_map',actual_mission=None,
                 pickup_verified=False,progress_verified=True,
                 persisted_clears=frozenset(('stg110','stg130')))
    observed=native.binding.attribute(snap,saved)
    assert observed.save_identity is None
    assert not journal.data.get('native_binding')

class ProfileMemory:
    def __init__(self,index=255): self.index=index
    def resolve_flags_ptr(self,*,allow_working=False):
        raise MemoryUnavailable('unknown_selected_slot')
    def resolve_save_container(self):
        return 0x90002000,0x90003000
    def read_u8(self,address):
        assert address==0x90003000
        return self.index


def test_c2_live_control_owner_can_match_real_unselected_index(monkeypatch):
    from ..client.state import live_control_profile
    journal,native,guard,snaps=initialize(monkeypatch)
    assert live_control_profile(ProfileMemory(),snaps[-1],guard) == (
        0x90002000,0x90003000,255,None,None)
    # This is NOT a writable selected-save address.
    assert journal.data['save_identity'] is None


def test_c2_no_slot_rejects_index_change_and_unattributed_scene(monkeypatch):
    from ..client.state import live_control_profile
    from dataclasses import replace
    journal,native,guard,snaps=initialize(monkeypatch)
    with pytest.raises(MemoryUnavailable,match='native index changed'):
        live_control_profile(ProfileMemory(254),snaps[-1],guard)
    with pytest.raises(MemoryUnavailable,match='no verified'):
        live_control_profile(ProfileMemory(),replace(snaps[-1],scene='global_map'),guard)


def test_c2_no_slot_rejects_wrong_session_after_bootstrap(monkeypatch):
    from ..client.state import live_control_profile
    journal,native,guard,snaps=initialize(monkeypatch)
    with pytest.raises(MemoryUnavailable,match='no verified'):
        live_control_profile(ProfileMemory(),replace(snaps[-1],session='other-boot'),guard)

@pytest.mark.parametrize('native_index',[4,5,254,255])
def test_transient_gecko_controls_use_actual_pal_index(monkeypatch,native_index):
    """Do not assume the no-slot byte is exactly 0xFF."""
    from copy import deepcopy
    from ..client.state import live_control_profile
    journal,native,guard,snaps=initialize(monkeypatch)
    trace=deepcopy(snaps[-1].evidence['save_chain_trace'])
    trace['steps'][0]['raw']=f'0x{native_index:02X}'
    observed=replace(snaps[-1],evidence={**snaps[-1].evidence,'save_chain_trace':trace})
    assert live_control_profile(ProfileMemory(native_index),observed,guard)==(
        0x90002000,0x90003000,native_index,None,None)
    # Any different byte, including the first valid selected save slot,
    # indicates a changed context and must be rejected.
    with pytest.raises(MemoryUnavailable,match='no-slot native index changed'):
        live_control_profile(ProfileMemory(native_index - 1),observed,guard)


@pytest.mark.parametrize('mismatch', [None, 'score', 'session', 'epoch', 'missing'])
def test_first_save_reconciles_durable_intro_after_reboot(monkeypatch, mismatch):
    journal,native,guard,snaps=initialize(monkeypatch)
    bootstrap=journal.data['bootstrap']
    journal.data['pickup_events']=[dict(kind='result',mission=m,score=score,
        grade=2,session=bootstrap['session'],playthrough_epoch=bootstrap['epoch'],
        provenance='stage9C_native_UI_state7_grade124')
        for m,score in [('stg110',12300),('stg130',15500)]]
    if mismatch=='session':journal.data['pickup_events'][0]['session']='unrelated'
    if mismatch=='epoch':journal.data['pickup_events'][0]['playthrough_epoch']='unrelated'
    if mismatch=='missing':journal.data['pickup_events'].pop()
    saved=dict(chain=(0,0,1),profile_hex='saved-profile',rank_records={
        m:dict(raw_rank=2,score=score,time_raw=140)
        for m,score in [('stg110',12301 if mismatch=='score' else 12300),('stg130',15500)]})
    snap=replace(snaps[-1],session='new-boot',scene='world_map',actual_mission=None,
        progress_verified=True,persisted_clears=frozenset(('stg110','stg130')))
    observed=SaveBinding(journal).attribute(snap,saved)
    assert observed.save_identity_verified == (mismatch is None)
    guard.observe(observed)
    assert (journal.data['save_identity']==bootstrap['epoch']) == (mismatch is None)
