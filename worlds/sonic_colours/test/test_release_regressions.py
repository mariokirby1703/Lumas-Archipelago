from collections import Counter
import pytest
from ..Items import ALL_WISP_ITEMS,GAME_LAND_SPEED,RING_VALUES
from ..settings import SonicColoursSettings
from . import generate


def test_empty_optional_paths_do_not_resolve_to_the_ap_directory():
    settings=SonicColoursSettings()
    for name in ('wit_path','dolphin_path'):
        assert name in settings
        value=getattr(settings,name)
        assert str(value)=='' and value.resolve()=='' and not value.exists()


@pytest.mark.parametrize('rings',['singles','per_level'])
@pytest.mark.parametrize('land',[False,True])
@pytest.mark.parametrize('super_sonic',[False,True])
@pytest.mark.parametrize('reduction',[0,99])
def test_small_check_sets_fit_without_removing_required_items(rings,land,super_sonic,reduction):
    multi=generate(dict(red_ring_checks=rings,rank_checks=0,one_up_sanity=False,
        wisp_discovery_checks=False,game_land_checks=land,eggman_heart_sanity=False,
        chaos_emerald_checks=False,movement_unlocks=True,super_sonic=super_sonic,
        game_land_requirement_reduction=reduction),seed=110,fill=True)
    world=multi.worlds[1]
    assert not multi.precollected_items[1]
    items=multi.itempool+multi.precollected_items[1]
    counts=Counter(i.name for i in items)
    assert sum(counts[n] for n in ALL_WISP_ITEMS)==11
    assert counts[GAME_LAND_SPEED]==(4 if land else 0)
    assert sum(RING_VALUES.get(i.name,0) for i in items)==world.ring_target
    assert len(multi.itempool)==len(world.active_locations)
    assert multi.can_beat_game() and not multi.get_unfilled_locations()
    assert any(loc.name=='Sonic Colours Victory' for loc in multi.get_locations())


@pytest.mark.parametrize('seed',range(10))
def test_restrictive_start_does_not_spend_intro_checks_on_unusable_shuttles(seed):
    multi=generate(dict(red_ring_checks=0,rank_checks=0,one_up_sanity=True,
        wisp_discovery_checks=False,movement_unlocks=True,boost_lock=True,
        game_land_checks=True,super_sonic=True,world_progression=0,
        game_land_requirement_reduction=27),seed=seed,fill=True)
    assert multi.can_beat_game() and not multi.get_unfilled_locations()
    assert multi.local_early_items[1].get('Progressive Crouch',0)+sum(
        item.name=='Progressive Crouch' for item in multi.precollected_items[1])==2


from pathlib import Path
import json
_CASES=json.loads((Path(__file__).parent/'fixtures/fuzz/waimea_2026_10_26.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case',_CASES,ids=lambda case:case['case'])
def test_reported_fill_failures(case):
    multi=generate(case['options'],seed=case['seed'],fill=True)
    assert not multi.precollected_items[1]
    assert multi.can_beat_game() and not multi.get_unfilled_locations()


@pytest.mark.parametrize('seed',range(3))
def test_two_players_fill_without_stranding_progression(seed):
    from Fill import distribute_items_restrictive
    from test.general import setup_multiworld
    from ..world import SonicColoursWorld
    multi=setup_multiworld([SonicColoursWorld,SonicColoursWorld],seed=seed)
    distribute_items_restrictive(multi)
    assert multi.can_beat_game() and not multi.get_unfilled_locations()


def test_red_ring_modes_and_legacy_off_slots():
    from ..Options import RedRingChecks
    from ..Locations import LOCATION_TABLE
    from ..client.runtime import validate_slot
    assert RedRingChecks.options=={'singles':1,'per_level':2}
    assert RedRingChecks.default==1
    for value in (0,False,'off','false'):
        multi=generate({'red_ring_checks':value})
        assert multi.worlds[1].options.red_ring_checks.value==1
        assert not multi.precollected_items[1]
    slot=generate().worlds[1].fill_slot_data()
    old={**slot,'options_revision':9,
         'options':{**slot['options'],'red_ring_checks':0},
         'locations':{name:code for name,code in slot['locations'].items()
                      if LOCATION_TABLE[name].kind not in ('ring','rings')}}
    assert validate_slot(old)['options']['red_ring_checks']==0
    with pytest.raises(ValueError):
        validate_slot({**old,'options_revision':10})


def test_large_red_ring_bundles_only_when_needed_and_ids_remain_stable():
    from ..Items import ITEM_TABLE, BY_ID
    from ..client.runtime import inventory
    from ..world_constants import BASE_ID,pack_rings
    assert ITEM_TABLE['Red Ring']==BASE_ID+23
    assert ITEM_TABLE['5 Red Rings']==BASE_ID+24
    assert ITEM_TABLE['10 Red Rings']==BASE_ID+25
    for name,offset in (('20 Red Rings',58),('50 Red Rings',59)):
        assert ITEM_TABLE[name]==BASE_ID+offset
        assert BY_ID[BASE_ID+offset]==name
    assert all(n<=10 for n in pack_rings(60,6))
    assert pack_rings(60,2)==(10,50)
    assert pack_rings(40,2)==(20,20)
    assert inventory([ITEM_TABLE['20 Red Rings'],ITEM_TABLE['50 Red Rings']])['red_rings']==70


_MAIN_CASES=json.loads((Path(__file__).parent/'fixtures/fuzz/waimea_2026_10_26_182415.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case',_MAIN_CASES,ids=lambda case:case['case'])
def test_reported_minimal_fills_through_main(case,tmp_path,monkeypatch):
    import random
    import yaml
    import Utils
    from Generate import main as roll,mystery_argparse
    from Main import main
    players=tmp_path/'players';players.mkdir()
    (players/'player.yaml').write_text(yaml.safe_dump(case['weights']),encoding='utf-8')
    output=tmp_path/'output'
    monkeypatch.setattr(Utils.output_path,'cached_path',str(output),raising=False)
    previous=random.getstate()
    try:
        args,seed=roll(mystery_argparse([
            '--player_files_path',str(players),'--weights_file_path','absent.yaml',
            '--meta_file_path','absent_meta.yaml','--seed',str(case['seed']),
            '--skip_output','--outputpath',str(output)]))
        multi=main(args,seed)
    finally:
        random.setstate(previous)
    assert not multi.precollected_items[1]
    assert multi.can_beat_game() and not multi.get_unfilled_locations()
    assert multi.worlds[1].options.accessibility.value==2
    assert all(loc.item.location is loc for loc in multi.get_filled_locations())


@pytest.mark.parametrize('seed',range(3))
def test_two_restrictive_players_fill_together(seed):
    from Fill import distribute_items_restrictive
    from test.general import setup_multiworld
    from ..world import SonicColoursWorld
    options=[case['weights'][SonicColoursWorld.game] for case in _MAIN_CASES]
    multi=setup_multiworld([SonicColoursWorld,SonicColoursWorld],seed=seed,options=options)
    distribute_items_restrictive(multi)
    assert multi.can_beat_game() and not multi.get_unfilled_locations()
    assert all(not items for items in multi.precollected_items.values())
    assert all(loc.item.location is loc for loc in multi.get_filled_locations())
