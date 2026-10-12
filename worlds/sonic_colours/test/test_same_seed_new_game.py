"""Fresh native restart keeps seed inventory/checks, never adopts loaded saves."""
from dataclasses import replace
import pytest
from ..client.journal import Journal
from ..client.state import SaveGuard,Snapshot,PlaythroughState
from ..client.binding import SaveBinding
from .test_runtime import IDENTITY


def fresh():return Snapshot('new-session',None,None,'gameplay','stg110',
    stage_epoch='new-intro',stable_polls=3,scene_verified=True,new_game_verified=True,
    fresh_fields=(True,True),pickup_verified=True,
    evidence={'native_intro_without_selected_slot':True})


def test_same_seed_new_game_reauthorizes_ephemeral_controls_and_preserves_ap(tmp_path):
    with Journal(tmp_path,IDENTITY) as j:
        j.data.update(save_identity='old-save',native_binding={'id':'old-save'},
            native_monotonic_clears=['stg110','stg130','stg140'],
            bootstrap={'epoch':'old-epoch','session':'old-session'},
            checks=[847001001],receipts=[847000029])
        g=SaveGuard(j);g.observe(fresh())
        assert g.state==PlaythroughState.MANDATORY_PROLOGUE
        assert j.data['save_identity'] is None and 'native_binding' not in j.data
        assert j.data['checks']==[847001001] and j.data['receipts']==[847000029]
        assert j.data['prior_playthroughs'][0]['save_identity']=='old-save'
        assert g.can_record_pickups(fresh())
        g.observe(fresh());assert len(j.data['prior_playthroughs'])==1
        assert g.can_record_pickups(replace(fresh(),actual_mission='stg130'))


@pytest.mark.parametrize('change',[{'new_game_verified':False},{'fresh_fields':(True,False)},
    {'scene':'world_map'},{'actual_mission':'stg130'},{'stable_polls':1},
    {'save_identity':'foreign','save_identity_verified':True}])
def test_restart_never_weakens_loaded_save_or_incomplete_proof(tmp_path,change):
    with Journal(tmp_path,IDENTITY) as j:
        j.data['save_identity']='old-save';g=SaveGuard(j)
        g.observe(replace(fresh(),**change))
        assert j.data['save_identity']=='old-save'
        assert 'prior_playthroughs' not in j.data


def test_restart_discards_in_memory_previous_intro_record_cache(tmp_path):
    with Journal(tmp_path,IDENTITY) as j:
        binding=SaveBinding(j);binding.intro_session='old-session'
        binding.second_act_seen=True;binding.first_record={'score':123}
        binding.observe_intro(fresh())
        assert not binding.second_act_seen and binding.first_record is None


def test_repeat_intro_results_produce_new_binding_witness_even_when_checked(tmp_path):
    from ..client.runtime import Runtime
    from ..client.hooks import NativeHooks
    from . import generate
    with Journal(tmp_path,IDENTITY) as j:
        j.data['save_identity']='old-save'
        slot=generate().worlds[1].fill_slot_data()
        j.data['checks']=list(slot['locations'].values())
        g=SaveGuard(j);g.observe(fresh())
        r=Runtime(slot,j,g,NativeHooks(j))
        r.snapshot=replace(fresh(),scene='results',current_result={
            'mission':'stg110','final':True,'grade':2,'score':123,
            'provenance':'stage9C_native_UI_state7_grade124'})
        r.observe_results();r.observe_results()
        events=[e for e in j.data['pickup_events'] if e['kind']=='result']
        assert len(events)==1 and events[0]['score']==123
        assert events[0]['playthrough_epoch']==j.data['bootstrap']['epoch']
        assert j.data['checks']==list(slot['locations'].values())
