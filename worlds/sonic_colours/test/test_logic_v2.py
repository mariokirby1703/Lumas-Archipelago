from collections import Counter
from types import SimpleNamespace
import itertools
import pytest
from BaseClasses import ItemClassification,CollectionState
from .. import logic_v2 as logic
from ..Items import ITEM_TABLE,ALL_WISP_ITEMS,RANDOM_CAPSULES
from ..world_constants import load_data,BASE_ID,STAGES
from ..wisps import required_wisp_items,project_inventory,wisp_level,all_wisps_owned
from ..client.runtime import inventory,validate_slot
from . import generate

class State:
    def __init__(self,items=()):self.items=Counter(items)
    def has(self,n,p,count=1):return self.items[n]>=count
    def count(self,n,p):return self.items[n]


def world(**options):
    return SimpleNamespace(player=1,options=SimpleNamespace(**{'boost_lock':True,'movement_unlocks':True,'game_land_checks':True,**options}))

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
    if land:assert next(i for i in multi.itempool if i.name==RANDOM_CAPSULES).classification==(ItemClassification.progression if capsules else ItemClassification.useful)
    assert multi.can_beat_game()
    assert validate_slot(w.fill_slot_data())['logic_policy']=='sheet_v2'
    owned=project_inventory(inventory([ITEM_TABLE[n] for n in required_wisp_items(w.options)]),w.fill_slot_data()['options'])
    assert all_wisps_owned(owned['counts'],w.options)
    assert wisp_level(owned['counts'],'Yellow Drill',w.options)==(1 if movement else 2)


def test_exact_location_coverage_and_source_mapping():
    d=load_data('logic_from_sheet_v2.json');assert logic.validate_manifest(d) is d
    assert len(d['locations'])==298
    assert d['locations']['stg130']['source']['tab']=='Tropical Resort'
    assert d['locations']['stg110']['wisp_availability_note']
    assert logic.check(world(),State(),d,'stg110') # Availability column is never a requirement.
    broken={**d,'locations':{k:v for k,v in d['locations'].items() if k!='stg130'}}
    with pytest.raises(ValueError,match='mismatch'):logic.validate_manifest(broken)


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
    assert data['options_revision']==9 and not data['game_land_speed_items']
    assert validate_slot(data)['game_land_speed_items'] is False
    old={**data,'options_revision':8,'game_land_speed_items':True}
    assert validate_slot(old)['game_land_speed_items'] is True
    with pytest.raises(ValueError,match='speed pool contract'):
        validate_slot({**data,'game_land_speed_items':True})

@pytest.mark.parametrize('colour,move',[('Yellow Drill','Yellow Drill Turbo'),('Green Hover','Green Hover Ring Dash'),('Pink Spikes','Pink Spikes Spin Dash')])
def test_special_moves_require_real_ownership_and_correct_tiers(colour,move):
    assert not logic.available(world(movement_unlocks=False),State(),{'ability':move})
    assert logic.available(world(movement_unlocks=False),State([colour+' Wisp']),{'ability':move})
    assert not logic.available(world(),State(['Progressive '+colour+' Wisp']),{'ability':move})
    assert logic.available(world(),State(['Progressive '+colour+' Wisp']*2),{'ability':move})


def test_or_of_and_progressive_tiers_and_conservative_review():
    w=world();entry={'status':'documented','routes':[[{'ability':'Cyan Laser'},{'ability':'Orange Rocket'}],[{'ability':'Pink Spikes'}]]}
    assert logic.entry_match(w,State(['Cyan Laser Wisp','Orange Rocket Wisp']),entry)
    assert logic.entry_match(w,State(['Progressive Pink Spikes Wisp']),entry)
    assert not logic.entry_match(w,State(['Cyan Laser Wisp']),entry)
    reviewed={**entry,'review':['check_and_or_precedence']}
    assert logic.entry_match(w,State(['Progressive Pink Spikes Wisp']),reviewed)
    assert not logic.entry_match(w,State(['Cyan Laser Wisp']),reviewed)
    assert not logic.available(w,State(['Progressive Crouch']),{'ability':'Progressive Crouch','tier':2})
    assert logic.available(world(movement_unlocks=False),State(),{'ability':'Progressive Crouch','tier':2})
    assert logic.available(world(game_land_checks=False),State(),{'ability':'Progressive Game Land Speed','tier':4})
    assert logic.available(world(movement_unlocks=False),State(),{'ability':'Progressive Game Land Speed','tier':4})


def test_rank_metadata_never_awards_a_native_result():
    from ..client.runtime import detect_checks
    from ..client.state import Snapshot
    w=generate({'rank_checks':'all'}).worlds[1]
    data=w.fill_slot_data();s=Snapshot(session='S',save_identity=None,visible_slot=0,actual_mission='stg110',scene='gameplay',awarded_ranks={})
    assert not any(code in detect_checks(data,s) for name,code in data['locations'].items() if 'Rank' in name)
    assert load_data('logic_from_sheet_v2.json')['rank_observations']['stg490']['rank_labels']['S']['time_limit_seconds']==200


def test_all_five_uses_each_individual_route():
    d={'locations':{}}
    for i in range(1,6):d['locations'][f'stg110:ring:{i}']={'mission_id':'stg110','normal':{'status':'documented','routes':[[{'ability':'Cyan Laser'}]] if i==5 else [[]]},'movement':{'status':'not_documented','routes':None}}
    assert not logic.all_five_rings(world(),State(),d,'stg110')
    assert logic.all_five_rings(world(),State(['Cyan Laser Wisp']),d,'stg110')


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


@pytest.mark.parametrize('boost,movement',tuple(itertools.product((0,1),repeat=2)))
def test_every_documented_sheet_route_can_be_satisfied_without_unavailable_variants(boost,movement):
    from ..Items import MOVEMENT_POOL
    w=world(boost_lock=boost,movement_unlocks=movement,game_land_checks=False)
    owned=State(list(required_wisp_items(w.options))*2+list(MOVEMENT_POOL))
    manifest=load_data('logic_from_sheet_v2.json')
    for key in manifest['locations']:
        assert logic.check(w,owned,manifest,key),key
    # The only unresolved rank strategy must not demand Assist Change when
    # Game Land checks have removed that item from the pool.
    owned.items.pop('Assist Change',None)
    assert logic.check(w,owned,manifest,'stg650','S')


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


def test_sheet_normal_or_routes_remain_alternatives():
    manifest=load_data('logic_from_sheet_v2.json')
    # These have explicit alternative routes; ambiguity remains documented
    # in the data rather than spuriously requiring every ability at once.
    assert logic.check(world(),State(['Progressive Green Hover Wisp']),manifest,'stg320:ring:4')
    assert logic.check(world(),State(['Progressive Pink Spikes Wisp']),manifest,'stg410')
    assert logic.check(world(movement_unlocks=False),
                       State(['Cyan Laser Wisp','Orange Rocket Wisp']),manifest,'stg430')
    assert not logic.check(world(),State(['Cyan Laser Wisp']),manifest,'stg430')


def test_ast_coaster_s_rank_skill_note_does_not_require_every_item():
    manifest=load_data('logic_from_sheet_v2.json')
    assert logic.check(world(),State(['Quick Step']),manifest,'stg650','S')
    assert not logic.check(world(),State(),manifest,'stg650','S')
    assert logic.check(world(movement_unlocks=False),State(),manifest,'stg650','S')
