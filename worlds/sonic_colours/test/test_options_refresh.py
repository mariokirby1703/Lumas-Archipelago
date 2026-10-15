from Options import get_option_groups,Visibility
from ..Options import SonicColoursOptions,WispCapsules,WorldProgression
from ..world import SonicColoursWorld
from ..Items import ITEM_TABLE,TRAPS
from ..world_constants import BASE_ID
from ..client.runtime import validate_slot
from . import generate


def test_defaults_groups_and_hidden_capsules():
    world=generate().worlds[1];options=world.options
    assert options.boost_lock.value==options.movement_unlocks.value==options.wisp_discovery_checks.value==1
    assert options.chaos_emerald_checks.value==0
    assert options.score_reset_trap_weight.value==1
    groups=get_option_groups(SonicColoursWorld)
    assert list(groups['Checks']).index('one_up_sanity')==list(groups['Checks']).index('rank_checks')+1
    assert set(groups['Game Land'])=={'game_land_checks','chaos_emerald_checks','eggman_heart_sanity','game_land_requirement_reduction'}
    assert set(groups['Miscellaneous'])=={'music_randomization','death_link'}
    visible={key for group in groups.values() for key in group}
    assert not {'wisp_capsules','ap_item_hud','swim_trap_weight','swim_trap_duration'}&visible
    assert WispCapsules.visibility==Visibility.none
    assert WispCapsules.from_any(True).value==1
    assert not {'ap_item_hud','swim_trap_weight','swim_trap_duration'}&set(SonicColoursOptions.type_hints)


def test_land_off_removes_both_land_abilities_even_with_other_land_checks():
    multiworld=generate({'game_land_checks':False,'chaos_emerald_checks':True,'eggman_heart_sanity':True})
    assert not any(i.name in ('Assist Change','Progressive Game Land Speed') for i in multiworld.itempool)
    validate_slot(multiworld.worlds[1].fill_slot_data())


def test_retired_trap_id_is_not_reassigned_and_choices_keep_yaml_aliases():
    assert 'Swim Everywhere Trap' not in ITEM_TABLE and 'Swim Everywhere Trap' not in TRAPS
    assert ITEM_TABLE['Ring Loss Trap']==BASE_ID+30
    assert ITEM_TABLE['Score Reset Trap']==BASE_ID+53
    assert WorldProgression.from_any('sequential').value==0
    assert WorldProgression.from_any('open_acts').value==1


def test_capsules_remain_available_in_explicit_yaml():
    world=generate({'wisp_capsules':True}).worlds[1]
    from ..Locations import LOCATION_TABLE
    assert any(LOCATION_TABLE[n].kind=='capsule' for n in world.active_locations)


def test_super_sonic_pool_toggle_and_removed_goal():
    from ..Items import EMERALDS
    from ..Options import Goal
    for enabled in (False,True):
        world=generate({'super_sonic':enabled}).worlds[1]
        emeralds=[i.name for i in world.multiworld.itempool if i.name in EMERALDS]
        assert sorted(emeralds)==(sorted(EMERALDS) if enabled else [])
        validate_slot(world.fill_slot_data())
    assert generate().worlds[1].options.super_sonic.value==0
    assert 'super_sonic' not in Goal.options
