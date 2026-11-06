from copy import deepcopy
from itertools import combinations
import hashlib
import json
from pathlib import Path
import pytest
import yaml
from Options import OptionSet
from ..Options import RankChecks
from ..Locations import LOCATION_TABLE
from ..world_constants import RANKS,GAME
from ..client.runtime import validate_slot,detect_checks
from ..client.client import slot_identity_digest
from . import generate
from .test_runtime import snapshot

SELECTIONS=[list(c) for size in range(5) for c in combinations(RANKS,size)]


def test_real_multiple_selection_and_yaml_generation():
    from Generate import roll_settings
    assert issubclass(RankChecks,OptionSet) and not RankChecks.supports_weighting
    assert set(RankChecks.valid_keys)=={'C','B','A','S'}
    for value in ('[C, A]','[C, S]','[B, A, S]','[]'):
        weights=yaml.safe_load('name: RankTest\ngame: '+GAME+'\n'+GAME+':\n  rank_checks: '+value)
        selected=roll_settings(weights).rank_checks.value
        assert selected==set(weights[GAME]['rank_checks'])
    assert RankChecks.from_any(['c','a','A']).value=={'C','A'}
    assert RankChecks.from_any('C, S').value=={'C','S'}


@pytest.mark.parametrize('raw,expected',[(0,set()),(1,{'S'}),(2,{'A'}),(3,{'B'}),(4,{'C'}),
    (6,set(RANKS)),('off',set()),('all',set(RANKS)),('a',{'A'})])
def test_legacy_yaml_values_keep_their_meaning(raw,expected):
    assert RankChecks.from_any(raw).value==expected


@pytest.mark.parametrize('bad',[['D'],['A',1],5,True,['off','A']])
def test_invalid_ranks_are_rejected(bad):
    with pytest.raises((ValueError,KeyError)):RankChecks.from_any(bad)


@pytest.mark.parametrize('selection',SELECTIONS)
def test_every_combination_controls_exactly_its_rank_locations(selection):
    multi=generate({'rank_checks':selection},41,fill=True)
    slot=multi.worlds[1].fill_slot_data()
    assert slot['options_revision']==15
    assert slot['options']['rank_checks']==sorted(selection)
    assert validate_slot(slot)==slot
    for name,row in LOCATION_TABLE.items():
        if row.kind=='rank':
            assert (name in slot['locations'])==(row.mission!='stg720' and RANKS[row.index] in selection)
    assert multi.can_beat_game() and not multi.get_unfilled_locations()


@pytest.mark.parametrize('selection',[['C','A'],['C','S'],['B','A','S']])
@pytest.mark.parametrize('grade',range(5))
def test_native_results_report_only_selected_satisfied_ranks(selection,grade):
    slot=generate({'rank_checks':selection}).worlds[1].fill_slot_data()
    checked=detect_checks(slot,snapshot(awarded_ranks={'stg790':grade}))
    actual={RANKS[row.index] for name,row in LOCATION_TABLE.items()
            if row.kind=='rank' and row.mission=='stg790' and row.code in checked}
    assert actual=={rank for rank in selection if RANKS.index(rank)>=grade}
    assert not detect_checks({'locations':{n:c for n,c in slot['locations'].items() if LOCATION_TABLE[n].kind=='rank'}},
                             snapshot(persisted_clears={'stg790'}))


@pytest.mark.parametrize('value',[0,1,2,3,4,6])
def test_old_seed_wire_value_and_journal_are_unchanged(value):
    old=generate({'rank_checks':value}).worlds[1].fill_slot_data()
    old['options_revision']=14
    old['options']['rank_checks']=value
    expected=hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest()
    normalized=validate_slot(deepcopy(old))
    assert normalized==old
    assert slot_identity_digest(normalized)==expected


@pytest.mark.parametrize('bad',[0,'all',['D'],['A','A'],['a'],[1],True])
def test_new_slot_requires_a_valid_resolved_selection(bad):
    slot=generate().worlds[1].fill_slot_data()
    slot['options']['rank_checks']=bad
    with pytest.raises(ValueError):validate_slot(slot)


def test_combination_patch_roundtrip(tmp_path):
    from ..patch import load_patch
    multi=generate({'rank_checks':['C','A']},41,fill=True)
    multi.worlds[1].generate_output(tmp_path)
    patch=load_patch(next(tmp_path.glob('*.apsoniccolours')))
    assert patch.slot_data==multi.worlds[1].fill_slot_data()
    assert patch.slot_data['options']['rank_checks']==['A','C']


@pytest.mark.parametrize('weights,expected',[({'all':1},set(RANKS)),({'off':1},set()),({'C':1},{'C'})])
def test_legacy_weighted_yaml_still_rolls_one_choice(weights,expected):
    from Generate import roll_settings
    document={'name':'LegacyRanks','game':GAME,GAME:{'rank_checks':weights}}
    original=deepcopy(document)
    assert roll_settings(document).rank_checks.value==expected
    assert document==original


def test_old_patch_keeps_integer_rank_wire_format(tmp_path):
    from ..patch import SonicColoursPatch,load_patch
    slot=generate({'rank_checks':'C'}).worlds[1].fill_slot_data()
    slot['options_revision']=14
    slot['options']['rank_checks']=4
    path=tmp_path/'old.apsoniccolours'
    SonicColoursPatch(str(path),1,'OldRankPlayer',slot_data=slot).write()
    assert load_patch(path).slot_data==slot
