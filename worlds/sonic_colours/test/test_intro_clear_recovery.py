from dataclasses import replace
from types import SimpleNamespace

import pytest

from . import generate
from .test_runtime import IDENTITY, snapshot
from ..Locations import LOCATION_TABLE
from ..client.journal import Journal
from ..client.runtime import Runtime
from ..client.state import SaveGuard


def setup(directory, *, legacy=False, grade=2):
    journal = Journal(directory,IDENTITY)
    chain = [1,2,0,3,4]
    bootstrap = {'session':'session','epoch':'epoch','checks':[], 'observed_missions':[],
                 'intro_stage_epoch':'act1','intro_proof':'native_factory_save_v1'}
    if not legacy:
        bootstrap.update(initial_clears=[],intro_chain=chain)
    journal.data['bootstrap'] = bootstrap
    journal.data['pickup_events'] = [{'kind':'red_ring','mission':'stg110','ring':1,
                                    'stage_epoch':'act1','playthrough_epoch':'epoch'}]
    records = {'stg110':{'raw_rank':grade,'score':758200,'time_raw':17497},
               'stg130':{'raw_rank':255,'score':0,'time_raw':0}}
    evidence = {'chain':chain,'native_data':{'saved_progress':{
        'chain':chain,'profile_hex':'23'*10+'00'*10,'rank_records':records}}}
    state = snapshot(save_identity=None,save_identity_verified=False,scene_verified=True,
        actual_mission='stg130',stage_epoch='act2',pickup_verified=True,progress_verified=True,
        persisted_clears=frozenset({'stg110'}),candidate_clears=frozenset({'stg110'}),evidence=evidence)
    guard = SaveGuard(journal)
    guard.observe(state)
    runtime = Runtime(generate({'rank_checks':'all'}).worlds[1].fill_slot_data(),journal,guard,SimpleNamespace())
    runtime.snapshot = state
    return journal,runtime


@pytest.mark.parametrize('legacy',[False,True])
@pytest.mark.parametrize('grade',[0,1,2,3,4])
def test_missed_intro_ui_recovers_native_clear_and_actual_rank_once(tmp_path,legacy,grade):
    journal,runtime = setup(tmp_path,legacy=legacy,grade=grade)
    try:
        runtime.recover_intro_clear()
        expected = {code for name,code in runtime.slot_data['locations'].items()
                    if LOCATION_TABLE[name].mission == 'stg110' and
                    (LOCATION_TABLE[name].kind == 'clear' or
                     LOCATION_TABLE[name].kind == 'rank' and grade <= LOCATION_TABLE[name].index)}
        assert set(journal.data['checks']) == expected
        assert journal.data['pickup_events'][-1]['grade'] == grade
        assert journal.data['pickup_events'][-1]['provenance'] == 'native_intro_act2_record_transition_v1'
        count = len(journal.data['pickup_events'])
        runtime.recover_intro_clear()
        assert len(journal.data['pickup_events']) == count
    finally:
        journal.close()


@pytest.mark.parametrize('failure',['session','chain','baseline','mission','clear','progress','rank','time','legacy_pickup','legacy_profile','legacy_old_records'])
def test_unattributed_or_historical_progress_never_backfills(tmp_path,failure):
    journal,runtime = setup(tmp_path,legacy=failure.startswith('legacy'))
    try:
        state = runtime.snapshot
        saved = state.evidence['native_data']['saved_progress']
        if failure == 'session': state = replace(state,session='other')
        if failure == 'chain': state.evidence['chain'] = [5,6,0,7,8]
        if failure == 'baseline': journal.data['bootstrap']['initial_clears'] = ['stg110']
        if failure == 'mission': state = replace(state,actual_mission='stg120')
        if failure == 'clear': state = replace(state,persisted_clears=frozenset())
        if failure == 'progress': state = replace(state,progress_verified=False)
        if failure == 'rank': saved['rank_records']['stg110']['raw_rank'] = 255
        if failure == 'time': saved['rank_records']['stg110']['time_raw'] = 0
        if failure == 'legacy_pickup': journal.data['pickup_events'] = []
        if failure == 'legacy_profile': saved['profile_hex'] = '00'*20
        if failure == 'legacy_old_records': saved['rank_records']['stg130']['raw_rank'] = 2
        runtime.snapshot = state
        runtime.recover_intro_clear()
        assert not journal.data['checks']
        assert not any(e['kind'] == 'result' for e in journal.data['pickup_events'])
    finally:
        journal.close()
