from collections import Counter
import itertools
import pytest
from BaseClasses import ItemClassification,CollectionState
from ..Items import ITEM_TABLE,ALL_WISP_ITEMS,RANDOM_CAPSULES
from ..world_constants import load_data,BASE_ID,STAGES
from ..wisps import required_wisp_items,project_inventory,wisp_level,all_wisps_owned
from ..client.runtime import inventory,validate_slot
from . import generate

@pytest.mark.parametrize('boost,movement,land,capsules',tuple(itertools.product((0,1),repeat=4)))
def test_exact_option_pools_native_projection_and_complete_seed(boost,movement,land,capsules):
    multi=generate(dict(boost_lock=boost,movement_unlocks=movement,game_land_checks=land,wisp_capsules=capsules),fill=True)
    w=multi.worlds[1];counts=Counter(i.name for i in multi.itempool)
    assert sum(counts[n] for n in ALL_WISP_ITEMS)==7+boost+3*movement
    for colour in ('Yellow Drill','Green Hover','Pink Spikes'):
        assert counts[colour+' Wisp']==1-movement
        assert counts['Progressive '+colour+' Wisp']==2*movement
    assert counts['White Boost Wisp']==boost
    assert counts['Progressive Game Land Speed']==4*land*movement
    assert counts[RANDOM_CAPSULES]==land
    if land:assert next(i for i in multi.itempool if i.name==RANDOM_CAPSULES).classification==(ItemClassification.progression if capsules or movement else ItemClassification.useful)
    assert multi.can_beat_game()
    assert validate_slot(w.fill_slot_data())['logic_policy']=='sheet_v2'
    owned=project_inventory(inventory([ITEM_TABLE[n] for n in required_wisp_items(w.options)]),w.fill_slot_data()['options'])
    assert all_wisps_owned(owned['counts'],w.options)
    assert wisp_level(owned['counts'],'Yellow Drill',w.options)==(1 if movement else 2)


def test_normal_ids_are_append_only_and_legacy_progressive_ids_decode():
    assert [ITEM_TABLE[c+' Wisp'] for c in ('Yellow Drill','Green Hover','Pink Spikes')]==[BASE_ID+55,BASE_ID+56,BASE_ID+57]
    assert len(set(ITEM_TABLE.values()))==len(ITEM_TABLE)
    for colour in ('Yellow Drill','Green Hover','Pink Spikes'):
        assert wisp_level(Counter({colour+' Wisp':1}),colour)==2
        assert wisp_level(Counter({'Progressive '+colour+' Wisp':1}),colour)==1
        assert wisp_level(Counter({'Progressive '+colour+' Wisp':1}),colour,{'movement_unlocks':False})==2
        assert wisp_level(Counter(),colour,{'movement_unlocks':False})==0


def test_speed_pool_contract_preserves_old_seeds_and_rejects_wrong_new_pool():
    data=generate({'movement_unlocks':False,'game_land_checks':True}).worlds[1].fill_slot_data()
    assert data['options_revision']==10 and not data['game_land_speed_items']
    assert validate_slot(data)['game_land_speed_items'] is False
    old={**data,'options_revision':8,'game_land_speed_items':True}
    assert validate_slot(old)['game_land_speed_items'] is True
    with pytest.raises(ValueError,match='speed pool contract'):
        validate_slot({**data,'game_land_speed_items':True})


def test_rank_metadata_never_awards_a_native_result():
    from ..client.runtime import detect_checks
    from ..client.state import Snapshot
    w=generate({'rank_checks':'all'}).worlds[1]
    data=w.fill_slot_data();s=Snapshot(session='S',save_identity=None,visible_slot=0,actual_mission='stg110',scene='gameplay',awarded_ranks={})
    assert not any(code in detect_checks(data,s) for name,code in data['locations'].items() if 'Rank' in name)


def test_native_death_and_dead_weight_options_do_not_require_test_opt_in():
    from ..world_constants import load_data
    flags=load_data('versions.json')['live_validation']
    assert not flags['deathlink'] and not flags['dead_weight']
    m=generate({'native_feature_tests':0,'death_link':1,'dead_weight_trap_weight':1,
                'trap_percentage':100,'ring_loss_trap_weight':'off',
                'score_reset_trap_weight':'off'},fill=True)
    options=validate_slot(m.worlds[1].fill_slot_data())['options']
    assert options['native_feature_tests']==0 and options['death_link']==1
    assert options['dead_weight_trap_weight']==1
    assert any(i.name=='Dead Weight Trap' for i in m.itempool)


@pytest.mark.parametrize('progression',[0,1])
def test_sequential_region_dependencies_are_independent_of_traversal_order(progression):
    import random
    from ..Items import ALL_WISP_ITEMS,MOVEMENT_POOL,WORLD_ITEMS
    for seed in range(10):
        m=generate({'world_progression':progression,'wisp_capsules':1},seed)
        # Force an unrelated ordering of outgoing map edges before the first
        # CollectionState traversal. All stage gates must still settle.
        for region in m.regions:random.Random(seed).shuffle(region.exits._list)
        state=CollectionState(m)
        for name in list(ALL_WISP_ITEMS)*2+list(MOVEMENT_POOL)+list(WORLD_ITEMS):state.collect(m.worlds[1].create_item(name),True)
        assert state.can_reach('Map Slot '+next(s['stage_slot_id'] for s in STAGES if s['mission_id']=='stg720'),'Region',1)


def test_legacy_slot_normalization_preserves_the_previous_journal_digest():
    import hashlib,json
    from ..client.client import slot_identity_digest
    data=generate({'movement_unlocks':0,'boost_lock':0}).worlds[1].fill_slot_data()
    from ..world_constants import game_land_gates
    legacy={**data,'options_revision':4,'game_land_speed_items':True,'logic_policy':'provisional_clears_conservative_pickups',
            'game_land_gates':game_land_gates(data['options']['game_land_requirement_reduction']),
            'options':{k:v for k,v in data['options'].items() if k!='native_feature_tests'}}
    expected=hashlib.sha256(json.dumps(legacy,sort_keys=True).encode()).hexdigest()
    normalized=validate_slot(legacy)
    assert normalized['options']['native_feature_tests']==0
    assert slot_identity_digest(normalized)==expected
    assert wisp_level({'Progressive Yellow Drill Wisp':1},'Yellow Drill',normalized['options'])==2
