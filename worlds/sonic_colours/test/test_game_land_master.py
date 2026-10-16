import pytest
from . import generate
from .. import Items,Locations
from ..client.runtime import validate_slot


@pytest.mark.parametrize('land',[False,True])
@pytest.mark.parametrize('hearts',[False,True])
@pytest.mark.parametrize('emeralds',[False,True])
def test_game_land_master_controls_subchecks_and_currency(land,hearts,emeralds):
    mw=generate(dict(game_land_checks=land,eggman_heart_sanity=hearts,
                     chaos_emerald_checks=emeralds),fill=True)
    world=mw.worlds[1]
    kinds={Locations.LOCATION_TABLE[n].kind for n in world.active_locations}
    assert ('medal' in kinds)==(land and hearts)
    assert ('emerald' in kinds)==(land and emeralds)
    assert 'ring' in kinds  # Physical ring checks are independent.
    assert any(i.name in Items.RING_VALUES for i in mw.get_items())==land
    assert bool(world.ring_required)==land
    assert world.options.eggman_heart_sanity.value==int(land and hearts)
    assert world.options.chaos_emerald_checks.value==int(land and emeralds)
    validate_slot(world.fill_slot_data())
    assert mw.can_beat_game()


def test_hidden_capsule_sanity_does_not_restore_game_land_currency():
    mw=generate(dict(game_land_checks=False,wisp_capsules=True))
    assert not any(i.name in Items.RING_VALUES for i in mw.itempool)
    assert any(Locations.LOCATION_TABLE[n].kind=='capsule' for n in mw.worlds[1].active_locations)
    validate_slot(mw.worlds[1].fill_slot_data())


def test_older_seed_keeps_original_subchecks():
    from types import SimpleNamespace
    from ..Options import SonicColoursOptions
    data=generate(dict(game_land_checks=False)).worlds[1].fill_slot_data()
    data['options_revision']=5
    data['options']={**data['options'],'eggman_heart_sanity':1,'chaos_emerald_checks':1}
    options=SimpleNamespace(**{n:SonicColoursOptions.type_hints[n].from_any(v) for n,v in data['options'].items()})
    data['locations']={n:d.code for n,d in Locations.LOCATION_TABLE.items()
                       if Locations.enabled(d,options,respect_game_land=False)}
    assert validate_slot(data)['locations']==data['locations']
