"""Percent option is a UI translation, not a rewrite of the original gate math."""
import pytest
from ..Options import GameLandRequirementReduction
from ..world_constants import game_land_gates,game_land_reduction_points
from ..client.runtime import validate_slot
from . import generate


@pytest.mark.parametrize('percentage,old_reduction',[(0,0),(1,2),(25,45),(50,90),(75,135),(99,179)])
def test_slider_preserves_exact_previous_gate_values(percentage,old_reduction):
    assert game_land_reduction_points(percentage)==old_reduction
    world=generate({'game_land_requirement_reduction':percentage}).worlds[1]
    assert world.gates==game_land_gates(old_reduction)
    data=world.fill_slot_data()
    assert data['options_revision']==8
    assert data['options']['game_land_requirement_reduction']==percentage
    assert validate_slot(data)['game_land_gates']==game_land_gates(old_reduction)


def test_percentage_range_defaults_and_monotonic():
    assert (GameLandRequirementReduction.range_start,
            GameLandRequirementReduction.range_end,
            GameLandRequirementReduction.default)==(0,99,50)
    values=[game_land_reduction_points(p) for p in range(100)]
    assert values[0]==0 and values[-1]==179
    assert all(a < b for a,b in zip(values,values[1:]))
    for bad in (-1,100,180,0.5,True,'50'):
        with pytest.raises(ValueError):game_land_reduction_points(bad)


def test_legacy_amounts_up_to_179_still_load_exactly_and_new_slots_reject_179():
    new=generate({'game_land_requirement_reduction':99}).worlds[1].fill_slot_data()
    assert game_land_reduction_points(new['options']['game_land_requirement_reduction'])==179
    for old_value in (0,40,90,179):
        old={**new,'options_revision':7,
             'game_land_gates':game_land_gates(old_value),
             'options':{**new['options'],'game_land_requirement_reduction':old_value}}
        assert validate_slot(old)['game_land_gates']==game_land_gates(old_value)
    # The old raw maximum cannot be supplied as a new percentage.
    with pytest.raises(ValueError):
        validate_slot({**new,'options':{**new['options'],
                       'game_land_requirement_reduction':179}})


def test_new_slot_does_not_accept_legacy_first_gate_overrides():
    data=generate().worlds[1].fill_slot_data()
    assert data['game_land_gates']['1-1']==0
    with pytest.raises(ValueError,match='slot Game Land gates mismatch'):
        validate_slot({**data,'game_land_gates':{**data['game_land_gates'],'1-1':1}})
