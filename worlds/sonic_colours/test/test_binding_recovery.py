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
