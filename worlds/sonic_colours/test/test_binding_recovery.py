import json
from types import SimpleNamespace
import pytest
from ..client.binding import SaveBinding

@pytest.mark.parametrize('mismatch',[None,'seed','profile','records','rollback'])
def test_recovery_requires_exact_prior_seed_and_native_witness(tmp_path,mismatch):
    identity=dict(seed='same',team=0,slot=1,revision='pal',game='sonic',slot_digest='new')
    records={m:dict(raw_rank=2,score=100,time_raw=120) for m in ('stg110','stg130')}
    binding=dict(id='witness',profile_hex='profile',selected_index=0,intro_record_witnesses=[records])
    old=dict(identity={**identity,'slot_digest':'old'},native_binding=binding,save_identity='witness',native_monotonic_clears=['stg110'],receipts=[1],effects={'0':{'state':'confirmed'}})
    if mismatch=='seed':old['identity']['seed']='other'
    saved=dict(profile_hex='other' if mismatch=='profile' else 'profile',chain=[0,0,0],rank_records=records)
    if mismatch=='records':saved['rank_records']={m:{**v,'score':101} for m,v in records.items()}
    (tmp_path/'old.json').write_text(json.dumps(old))
    data=dict(save_identity=None,receipts=[1],effects={})
    journal=SimpleNamespace(path=tmp_path/'new.json',identity=identity,data=data,save=lambda:None)
    snapshot=SimpleNamespace(progress_verified=True,persisted_clears=frozenset() if mismatch=='rollback' else frozenset(['stg110']))
    SaveBinding(journal).recover_prior_binding(snapshot,saved)
    assert (data['save_identity']=='witness')==(mismatch is None)
    if mismatch is None:assert data['effects']['0']['state']=='confirmed'


@pytest.mark.parametrize('recovered',[False,True])
def test_recovered_pickup_without_epoch_is_restored_only_with_bound_recovery(recovered):
    from ..client.physical_rings import witnessed
    journal=SimpleNamespace(data=dict(save_identity='witness',native_binding=dict(id='witness',bootstrap_epoch='epoch'),
        binding_recovery='exact native witness from prior slot-data digest' if recovered else None,
        pickup_events=[dict(kind='red_ring',mission='stg160',ring=1,playthrough_epoch=None)]))
    assert witnessed(journal)==({'stg160':1} if recovered else {})


@pytest.mark.parametrize('change',['score_up','score_down','time','rank','profile','rollback'])
def test_bound_resume_accepts_only_score_improvement_with_stable_witnesses(change):
    from copy import deepcopy
    from .test_runtime import snapshot
    records={m:dict(raw_rank=2,score=100,time_raw=120) for m in ('stg110','stg130')}
    binding=dict(id='bound',kind='native_intro_record_witness_v1',profile_hex='profile',selected_index=0,intro_record_witnesses=[deepcopy(records)])
    data=dict(native_binding=binding,save_identity='bound',native_monotonic_clears=['stg110','stg130'])
    journal=SimpleNamespace(data=data,save=lambda:None)
    saved=dict(profile_hex='profile',chain=[0,0,0],rank_records=deepcopy(records))
    if change=='score_up':saved['rank_records']['stg130']['score']=101
    if change=='score_down':saved['rank_records']['stg130']['score']=99
    if change=='time':saved['rank_records']['stg130']['time_raw']=121
    if change=='rank':saved['rank_records']['stg130']['raw_rank']=1
    if change=='profile':saved['profile_hex']='other'
    if change=='rollback':saved['rank_records']['stg130']['score']=101
    snap=snapshot(progress_verified=True,persisted_clears=frozenset(['stg110'] if change=='rollback' else ['stg110','stg130']))
    result=SaveBinding(journal).attribute(snap,saved)
    assert result.save_identity_verified==(change=='score_up')
