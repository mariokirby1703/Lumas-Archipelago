"""No-AP-receipt, session-scoped manual ability overrides."""
from collections import Counter
import pytest
from ..Items import ITEM_TABLE, WISP_ITEMS, EMERALDS, RING_VALUES
from ..client.runtime import inventory
from ..client.test_inventory import (LocalInventoryOverrides, resolve_item,
                                     parse_item_request, TESTABLE, ABILITY_SET)


def genuine(*names):
    return inventory([ITEM_TABLE[name] for name in names])


def test_give_remove_virtual_double_jump_and_original_not_modified():
    original=genuine()
    overlay=LocalInventoryOverrides()
    assert overlay.change('give','Double Jump',1,original)['effective']==1
    assert overlay.apply(original)['counts']['Double Jump']==1
    assert original['counts']['Double Jump']==0
    assert overlay.change('remove','Double Jump',1,original)['effective']==0
    assert not overlay.deltas


def test_remove_real_item_and_reset():
    original=genuine('White Boost Wisp','Double Jump')
    overlay=LocalInventoryOverrides()
    overlay.change('remove','White Boost Wisp',1,original)
    assert overlay.apply(original)['wisps']==[]
    assert overlay.apply(original)['counts']['Double Jump']==1
    assert original['counts']['White Boost Wisp']==1
    overlay.change('give','White Boost Wisp',1,original)
    assert not overlay.deltas
    overlay.change('remove','Double Jump',1,original)
    assert overlay.apply(original)['counts']['Double Jump']==0
    overlay.reset()
    assert overlay.apply(original)['counts']['Double Jump']==1


def test_breathing_and_crouch_stages():
    original=genuine('Progressive Crouch','Progressive Breathing')
    overlay=LocalInventoryOverrides()
    assert overlay.change('give','Progressive Crouch','all',original)['effective']==2
    assert overlay.change('give','Progressive Breathing',5,original)['effective']==5
    assert overlay.apply(original)['counts']['Progressive Crouch']==2
    assert overlay.apply(original)['counts']['Progressive Breathing']==5
    assert overlay.change('remove','Progressive Breathing',2,original)['effective']==3
    assert overlay.change('remove','Progressive Crouch','all',original)['effective']==0
    assert overlay.apply(original)['counts']['Progressive Crouch']==0


def test_each_progression_and_wisp_item():
    base=genuine()
    for name in TESTABLE:
        overlay=LocalInventoryOverrides()
        overlay.change('give',name,1,base)
        assert overlay.apply(base)['counts'][name]==1
        overlay.change('remove',name,1,base)
        assert overlay.apply(base)['counts'][name]==0
    overlay=LocalInventoryOverrides()
    overlay.change_all_abilities('give',base)
    owned=overlay.apply(base)
    assert all(owned['counts'][name] for name in ABILITY_SET)
    assert owned['counts']['Progressive Crouch']==2
    assert owned['counts']['Progressive Breathing']==5
    overlay.change_all_abilities('remove',base)
    assert all(not overlay.apply(base)['counts'][name] for name in ABILITY_SET)


def test_effective_derived_fields_and_immutable_history():
    original=genuine('Green Chaos Emerald','Cyan Laser Wisp', 'Red Ring')
    overlay=LocalInventoryOverrides()
    for name in EMERALDS:
        overlay.change('give',name,1,original)
    overlay.change('remove','Cyan Laser Wisp','all',original)
    owned=overlay.apply(original)
    assert owned['super_sonic_allowed']
    assert not owned['wisps']
    assert owned['red_rings']==sum(original['counts'][n]*amount for n,amount in RING_VALUES.items())
    assert not original['super_sonic_allowed']
    assert original['wisps']==['Cyan Laser Wisp']


@pytest.mark.parametrize('raw,expected,qty',[
    ('Double Jump','Double Jump',1),
    ('"White Boost Wisp"','White Boost Wisp',1),
    ('white boost','White Boost Wisp',1),
    ('cyan','Cyan Laser Wisp',1),
    ('progressive breathing 5','Progressive Breathing',5),
    ('Crouch 2','Progressive Crouch',2),
    ('progressive crouch all','Progressive Crouch','all'),
    ('Swim','Swim',1),
    ('Breath','Progressive Breathing',1),
    ('breath 2','Progressive Breathing',2),
    ('legacy breath','Breath',1),
])
def test_parser(raw,expected,qty):
    assert parse_item_request(raw)==(expected,qty)


@pytest.mark.parametrize('raw,expected', [
    ('laser', 'Cyan Laser Wisp'),
    ('drill', 'Yellow Drill Wisp'),
    ('rocket', 'Orange Rocket Wisp'),
    ('cube', 'Blue Cube Wisp'),
    ('hover', 'Green Hover Wisp'),
    ('spikes', 'Pink Spikes Wisp'),
    ('frenzy', 'Purple Frenzy Wisp'),
    ('boost', 'White Boost Wisp'),
])
def test_wisp_power_names(raw, expected):
    assert resolve_item(raw) == expected
    assert parse_item_request(raw) == (expected, 1)


@pytest.mark.parametrize('level,seconds', [(0,0),(1,5),(2,10),(3,20),(4,40),(5,60)])
def test_breath_alias_sets_exact_tier_and_native_duration(level, seconds):
    from worlds.sonic_colours.client.water_native import duration
    original = genuine('Progressive Breathing','Progressive Breathing',
                       'Progressive Breathing','Progressive Breathing')
    overlay = LocalInventoryOverrides()
    if level:
        name, count = parse_item_request('breath ' + str(level))
        result = overlay.change('give', name, count, original)
    else:
        name, count = parse_item_request('breath all')
        result = overlay.change('remove', name, count, original)
    assert result['effective'] == level
    assert duration(overlay.apply(original)['counts']) == seconds
    assert original['counts']['Progressive Breathing'] == 4


def test_legacy_breath_is_masked_by_explicit_progressive_tier():
    from worlds.sonic_colours.client.water_native import duration
    original = genuine('Breath','Progressive Breathing','Progressive Breathing',
                       'Progressive Breathing','Progressive Breathing')
    overlay = LocalInventoryOverrides()
    overlay.change('give','Progressive Breathing',2,original)
    counts = overlay.apply(original)['counts']
    assert counts['Progressive Breathing'] == 2
    assert counts['Breath'] == 0
    assert duration(counts) == 10
    overlay.reset()
    assert duration(overlay.apply(original)['counts']) == 30


def test_removing_breathing_levels_is_subtractive():
    original = genuine()
    overlay=LocalInventoryOverrides()
    overlay.change('give','Progressive Breathing',4,original)
    assert overlay.change('remove','Progressive Breathing',2,original)['effective'] == 2
    assert overlay.change('remove','Progressive Breathing','all',original)['effective'] == 0


def test_crouch_explicit_number_is_a_target_tier():
    original = genuine('Progressive Crouch','Progressive Crouch')
    overlay=LocalInventoryOverrides()
    assert overlay.change('give','Progressive Crouch',1,original)['effective'] == 1
    assert overlay.apply(original)['counts']['Progressive Crouch'] == 1


@pytest.mark.parametrize('raw', ['Rings', 'Half Boost Refill', 'Full Boost Refill',
                                   'Ring Loss Trap', 'Swim Everywhere Trap', 'Not An Item'])
def test_reject_consumables_and_traps(raw):
    with pytest.raises(ValueError): resolve_item(raw)


def test_invalid_quantity_and_ambiguous():
    for raw in ('Double Jump 0', 'Double Jump 100', '"White Boost Wisp', 'Dance'):
        with pytest.raises(ValueError):parse_item_request(raw)
