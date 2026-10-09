from pathlib import Path
from collections import Counter
from dataclasses import replace
import struct
import pytest
import yaml
from BaseClasses import CollectionState
from ..Items import EMERALDS,ITEM_TABLE,RING_VALUES,WISP_ITEMS,WORLD_ITEMS
from ..Options import OPTION_NAMES,StartingAct,Goal,SonicColoursOptions
from ..world_constants import STARTING_STAGES,STAGES,BASE_ID,pack_rings
from ..client.runtime import inventory,victory,validate_slot,Runtime
from ..client.journal import Journal
from ..client.state import SaveGuard,WritePolicy
from ..client.memory import SonicMemory,MemoryUnavailable
from ..client.hooks import NativeHooks
from ..client.progression_hook import HOOK,ORIGINAL,payload,installed_data
from ..client.music import mapping_for,apply_music,cue_records
from ..migration import migrate_yaml
from .test_native_originals import PAIRS
from .test_pickup_integration import Overlay
from .test_runtime import IDENTITY,snapshot
from . import generate


def test_schema_and_stable_emerald_ids():
    assert EMERALDS == tuple(c+' Chaos Emerald' for c in ('Green','Red','Blue','Yellow','Purple','Cyan','White'))
    assert [ITEM_TABLE[n] for n in EMERALDS] == list(range(BASE_ID+15,BASE_ID+22))
    assert not {'wisp_unlocks','world_unlocks','chaos_emerald_items','red_ring_bundle_strategy','wisp_capsule_sanity'} & set(OPTION_NAMES)
    assert set(Goal.options) == {'nega_wisp_armor','all_bosses','all_red_rings','all_game_land_stages','super_sonic'}
    assert StartingAct.default == 'random' and len(StartingAct.options) == 44
    assert len(STARTING_STAGES) == 44 and 'stg790' not in {s['mission_id'] for s in STARTING_STAGES}
    assert sum(s['kind']=='Boss' for s in STARTING_STAGES) == 6


@pytest.mark.parametrize('checks',['singles','per_level','off'])
@pytest.mark.parametrize('goal',list(Goal.options))
def test_goals_and_ring_pool_reachability(checks,goal):
    for seed in range(8):
        m=generate({'red_ring_checks':checks,'goal':goal},seed,fill=True)
        w=m.worlds[1]
        assert m.can_beat_game() and not m.get_unfilled_locations()
        counts=Counter(i.name for i in m.itempool)
        assert all(counts[n] == 1 for n in EMERALDS)
        assert sum(RING_VALUES.get(i.name,0) for i in m.itempool) == 187
        if checks=='singles':
            assert counts['Red Ring (+1)']==187 and not counts['Red Rings (+5)'] and not counts['Red Rings (+10)']
        else:assert counts['Red Rings (+5)'] + counts['Red Rings (+10)'] > 0
        validate_slot(w.fill_slot_data())


@pytest.mark.parametrize('target,capacity',[(187,200),(187,88),(187,52),(17,14),(241,31)])
def test_exact_capacity_and_optimal_single_count(target,capacity):
    result=pack_rings(target,capacity)
    assert sum(result)==target and len(result)<=capacity
    best=max(target-10*t-5*f for t in range(target//10+1) for f in range((target-10*t)//5+1)
             if target-10*t-5*f+t+f<=capacity)
    assert result.count(1)==best


def test_goals_use_physical_pickups_bosses_and_owned_emeralds():
    data=generate().worlds[1].fill_slot_data()
    bosses=frozenset(s['mission_id'] for s in STAGES if s['kind']=='Boss')
    d={**data,'options':{**data['options'],'goal':1}}
    assert victory(d,snapshot(persisted_clears=bosses))
    assert not victory(d,snapshot(persisted_clears=bosses-{'stg790'}))
    d['options']['goal']=4
    assert victory(d,snapshot(),owned=inventory([ITEM_TABLE[n] for n in EMERALDS]))
    assert not victory(d,snapshot(),owned=inventory([ITEM_TABLE[n] for n in EMERALDS[:-1]]))
    d['options']['goal']=2
    masks={s['mission_id']:31 for s in STAGES if s['normal']}
    assert victory(d,snapshot(),masks)
    masks['stg110']=30
    assert not victory(d,snapshot(),masks)


def test_red_ring_goal_tracks_when_location_checks_are_off(tmp_path):
    data=generate({'red_ring_checks':'off','goal':'all_red_rings'}).worlds[1].fill_slot_data()
    value=snapshot(save_identity=None,scene_verified=True,pickup_verified=True,stage_epoch='intro',actual_mission='stg110',
                   new_game_verified=True,fresh_fields=(True,True))
    class Hooks:
        def snapshot(self,memory):return value
    with Journal(tmp_path,IDENTITY) as j:
        g=SaveGuard(j);r=Runtime(data,j,g,Hooks());g.observe(value);r.snapshot=value;r.observe_pickups()
        r.snapshot=replace(value,active_rings={'stg110':frozenset({1})});r.observe_pickups()
        assert j.data['ever_collected_mask']['stg110']==1 and not j.data['pickup_checks']


def test_capsule_rules_only_require_their_colour():
    m=generate({'wisp_capsules':True})
    from ..capsules import CAPSULES
    c=next(c for c in CAPSULES.values() if c.eligible and c.mission=='stg110' and c.wisp_item=='Cyan Laser Wisp')
    state=CollectionState(m)
    assert not m.get_location(c.name,1).access_rule(state)
    state.collect(m.worlds[1].create_item('Cyan Laser Wisp'))
    assert m.get_location(c.name,1).access_rule(state)


def test_supplied_yaml_migrates_and_generates():
    path=Path(__file__).parents[1]/'examples/Luma_Migrated.yaml'
    doc=yaml.safe_load(path.read_text())
    m=generate(doc['Sonic Colours (Wii)'],fill=True)
    assert m.can_beat_game() and m.worlds[1].ring_target==187
    old={'Sonic Colours (Wii)':{'goal':'all_story_clears','wisp_capsule_sanity':'story','wisp_unlocks':'vanilla','world_unlocks':'vanilla','chaos_emerald_items':False}}
    new,changes=migrate_yaml(old)
    assert new['Sonic Colours (Wii)']=={'goal':'all_bosses','wisp_capsules':True} and changes
    with pytest.raises(ValueError,match='schema migration'):
        validate_slot({**m.worlds[1].fill_slot_data(),'schema_version':2})


def install_progression(b):
    target=0x80002000;words,offset=payload()
    words[-1]=0x48000000 | ((HOOK+4-(target+len(words)*4-4))&0x3fffffc)
    b.write_bytes(target,struct.pack('>'+'I'*len(words),*words))
    b.write_bytes(HOOK,(0x48000000|((target-HOOK)&0x3fffffc)).to_bytes(4,'big'))
    return target+offset


@pytest.mark.skipif(not PAIRS,reason='private original capture absent')
def test_progression_payload_and_data_allowlist(tmp_path):
    b=Overlay(PAIRS[0]);m=SonicMemory(b)
    address=install_progression(b)
    assert installed_data(m)==address
    m.verify_revision()
    with Journal(tmp_path,IDENTITY) as j:
        h=NativeHooks(j);g=SaveGuard(j);r=Runtime(generate().worlds[1].fill_slot_data(),j,g,h)
        m.write_guard=WritePolicy(m,g,h.snapshot)
        for _ in range(3):r.poll(m,[],False)
        r.project_permissions(m,inventory([ITEM_TABLE['Cyan Laser Wisp']]))
        assert m.read_u32(address)==m.resolve_flags_ptr(allow_working=True)[-1]
        assert m.read_u32(address+4)==1<<20 and m.read_u32(address+8)==2
        before=len(b.writes)
        with pytest.raises(MemoryUnavailable):m.write_u32(address+12,0,expected=0,operation='progression_data')
        assert len(b.writes)==before
        with pytest.raises(MemoryUnavailable):m.write_u32(address+12,0,expected=0,operation='progression_reset')
        assert len(b.writes)==before
        b.write_bytes(address+8,(0x100).to_bytes(4,'big'))
        with pytest.raises(MemoryUnavailable,match='data is invalid'):m.verify_revision()


@pytest.mark.skipif(not PAIRS,reason='private original capture absent')
def test_native_music_table_redirects_readback(tmp_path):
    pair=next(p for p in PAIRS if '205502' in p[0].name)
    b=Overlay(pair);m=SonicMemory(b)
    slot=generate({'music_randomization':'anywhere'}).worlds[1].fill_slot_data()
    class Attributed:
        def check(self,s):return 'fixture attributed map'
    h=NativeHooks();m.write_guard=WritePolicy(m,Attributed(),h.snapshot)
    before={mission:m.read_bytes(a,32) for mission,a in cue_records(m)[3].items()}
    status=apply_music(m,slot)
    assert status['changed_cues']>0 and not status['audible_verified']
    assert mapping_for(slot)==mapping_for(slot)
    for mission,address in cue_records(m)[3].items():
        assert m.read_bytes(address,32).split(b'\0',1)[0].decode()==mapping_for(slot)[mission]
    assert apply_music(m,slot)['changed_cues']==0


def test_seven_discoveries_have_stage_regions_and_real_fill():
    from ..Locations import LOCATION_TABLE, DISCOVERY_STAGES
    for seed in range(10):
        m=generate({'wisp_discovery_checks':True},seed,fill=True)
        locations=[l for l in m.get_locations(1) if l.address and LOCATION_TABLE[l.name].kind=='wisp']
        assert len(locations)==7 and m.can_beat_game()
        for l in locations:
            d=LOCATION_TABLE[l.name]
            assert d.mission and l.parent_region.name.startswith('Map Slot ')


@pytest.mark.skipif(not PAIRS,reason='private original capture absent')
def test_music_off_restores_prior_seed_native_redirect():
    pair=next(p for p in PAIRS if '205502' in p[0].name)
    m=SonicMemory(Overlay(pair))
    class Attributed:
        def check(self,s):return 'fixture attributed map'
    h=NativeHooks();m.write_guard=WritePolicy(m,Attributed(),h.snapshot)
    slot=generate({'music_randomization':'anywhere'}).worlds[1].fill_slot_data()
    assert apply_music(m,slot)['changed_cues']>0
    vanilla=generate({'music_randomization':'off'}).worlds[1].fill_slot_data()
    assert apply_music(m,vanilla)['changed_cues']>0
    from ..world_constants import NORMAL
    expected={s['mission_id']:s['bgm'] for s in NORMAL}
    for mission,address in cue_records(m)[3].items():
        assert m.read_bytes(address,32).split(b'\0',1)[0].decode()==expected[mission]


@pytest.mark.skipif(not PAIRS,reason='private original capture absent')
def test_previous_seed_hook_events_are_baselined_not_credited(tmp_path):
    from ..Locations import LOCATION_TABLE
    b=Overlay(PAIRS[0]);m=SonicMemory(b);address=install_progression(b)
    b.write_bytes(address+12,(0x7f).to_bytes(4,'big'))
    b.write_bytes(address+16,(0x1fffff).to_bytes(4,'big'))
    with Journal(tmp_path,{**IDENTITY,'seed':'different fresh seed'}) as j:
        h=NativeHooks(j);g=SaveGuard(j)
        r=Runtime(generate({'wisp_discovery_checks':True}).worlds[1].fill_slot_data(),j,g,h)
        m.write_guard=WritePolicy(m,g,h.snapshot)
        for _ in range(3):r.poll(m,[],False)
        assert j.data['native_event_baseline']=={'discoveries':0,'game_land_clears':0}
        assert m.read_u32(address+12)==m.read_u32(address+16)==0
        assert not h.snapshot(m).discovered_wisps
        # Reusing a bit previously set by the old seed must now be reportable.
        b.write_bytes(address+12,(2).to_bytes(4,'big'))
        assert h.snapshot(m).discovered_wisps==frozenset({1})
        b.write_bytes(address+12,bytes(4))
        assert not any(LOCATION_TABLE[name].kind in ('wisp','emerald') and code in j.data['checks']
                       for name,code in r.slot_data['locations'].items())


@pytest.mark.parametrize('starting',range(44))
def test_every_starting_act_has_a_fillable_seed(starting):
    m=generate({'starting_act':starting},starting,fill=True)
    assert m.can_beat_game() and not m.get_unfilled_locations()
    assert m.worlds[1].starting_stage['mission_id']!='stg790'


@pytest.mark.parametrize('goal',range(5))
def test_capsule_and_rank_checks_fill_with_every_goal(goal):
    from ..Locations import LOCATION_TABLE
    m=generate({'goal':goal,'wisp_capsules':True,'rank_checks':'all','starting_act':42},goal,fill=True)
    assert m.can_beat_game() and not m.get_unfilled_locations()
    assert sum(LOCATION_TABLE[l.name].kind=='capsule' for l in m.get_locations(1) if l.address)==680
