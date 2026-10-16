import itertools
import pytest
from . import generate
from ..Options import Goal
from ..client.runtime import validate_slot,detect_checks
from .test_runtime import snapshot


@pytest.mark.parametrize('goal,land,movement,boost',list(itertools.product(range(3),(0,1),(0,1),(0,1))))
def test_remaining_goal_option_matrix_is_beatable(goal,land,movement,boost):
    mw=generate(dict(goal=goal,game_land_checks=land,movement_unlocks=movement,boost_lock=boost),
                seed=100+goal*8+land*4+movement*2+boost,fill=True)
    validate_slot(mw.worlds[1].fill_slot_data())
    assert mw.can_beat_game() and not mw.get_unfilled_locations()


def test_retired_game_land_goal_is_not_selectable_or_reassigned():
    assert set(Goal.options.values())=={0,1,2}
    for value in (3,'all_game_land_stages'):
        with pytest.raises((ValueError,KeyError)):generate(dict(goal=value))


def test_legacy_game_land_goal_still_loads_but_new_slot_rejects_it():
    data=generate().worlds[1].fill_slot_data()
    data['options']={**data['options'],'goal':3}
    with pytest.raises((ValueError,KeyError)):validate_slot(data)
    data['options_revision']=6
    assert validate_slot(data)['options']['goal']==3


def test_legacy_super_sonic_goal_remains_supported():
    data=generate().worlds[1].fill_slot_data()
    data['options_revision']=2
    data['options']={**data['options'],'goal':4}
    data['logic_policy']='provisional_clears_conservative_pickups'
    assert validate_slot(data)['options']['goal']==4
