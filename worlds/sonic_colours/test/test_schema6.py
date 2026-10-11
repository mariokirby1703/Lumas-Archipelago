"""Schema 6 tests use real original PAL memory captures when available."""
from pathlib import Path
import pytest
from ..Options import OPTION_NAMES
from ..world_constants import STAGES, SCHEMA_VERSION
from ..world_progression import available_story_stages
from ..client import live_music, music_bank, direct_hooks
from ..client.memory import SonicMemory, MemoryUnavailable
from . import generate


def test_new_public_options_and_unchanged_medal_ids():
    assert SCHEMA_VERSION == 6
    assert 'starting_act' not in OPTION_NAMES and 'level_randomization' not in OPTION_NAMES
    assert {'eggman_heart_sanity','world_progression','music_randomization'} <= set(OPTION_NAMES)
    for mode in (0,1):
        w = generate({'world_progression':mode,'eggman_heart_sanity':True},mode,fill=True)
        slot=w.worlds[1].fill_slot_data()
        assert slot['starting_world']==0 and 'starting_slot' not in slot
        assert w.can_beat_game() and not w.get_unfilled_locations()
        assert sum(name.endswith(' - Eggman Heart') for name in slot['locations'])==21
        assert {code for name,code in slot['locations'].items() if name.endswith(' - Eggman Heart')} == set(range(847005000,847005021))


@pytest.mark.parametrize('zone',range(6))
def test_both_native_story_progression_policies(zone):
    acts=tuple(s['mission_id'] for s in STAGES if s['zone_index']==zone and 1<=s['slot']<=6)
    boss=next(s['mission_id'] for s in STAGES if s['zone_index']==zone and s['slot']==7)
    assert len(acts)==6
    assert available_story_stages(zone,set(),0)=={acts[0]}
    assert available_story_stages(zone,set(),1)==set(acts)
    assert available_story_stages(zone,set(acts[:2]),0)==set(acts[:3])
    assert boss not in available_story_stages(zone,set(acts[:5]),1)
    assert boss not in available_story_stages(zone,{acts[-1]},0)
    for mode in (0,1):
        assert boss in available_story_stages(zone,set(acts),mode)


def test_native_patch_plan_stays_within_disabled_gecko_scratch():
    hooks=direct_hooks.plan()
    assert len(hooks)==10 and all(hook!=0 for hook,_,_,_,_ in hooks)
    assert len({hook for hook,_,_,_,_ in hooks})==len(hooks)
    assert hooks[0][2]==direct_hooks.ARENA_START
    assert hooks[-1][2]+len(hooks[-1][3]) <= direct_hooks.ARENA_END
    assert sum(len(code) for _,_,_,code,_ in hooks) < direct_hooks.ARENA_END-direct_hooks.ARENA_START


def test_bgm_87_cues_seed_permutation_and_safe_recovery():
    assert len(music_bank.CUES)==87
    # Every genuine music cue participates, including musical jingles.
    perm=music_bank.plan('schema6-test','anywhere')
    assert set(perm)==set(music_bank.CUES)
    assert len(perm) == 87 and all(perm[n]!=n for n in perm)
    assert any(perm[n]!=n for n in ('bgm_wmap', 'bgm_mlt_a', 'bgm_sys_title'))


def test_actual_original_ram_bank_can_be_rewritten_without_game_files():
    mem2=Path(__file__).parents[1] / 'notes/items_wisps_20261009/mem2(20261009-184953).raw'
    if not mem2.exists():pytest.skip('original MEM2 capture not supplied')
    with mem2.open('rb') as stream:
        stream.seek(0x17e8a0)
        data=stream.read(live_music.ORIGINAL_SIZE)
    assert live_music.recover_original(data)==data
    result=music_bank.rewrite_bank(data,music_bank.plan('schema6-test','anywhere'))
    assert len(result)==len(data) and result!=data
    assert live_music.recover_original(result)==data
    with pytest.raises(MemoryUnavailable):live_music.recover_original(result[:-1]+bytes([result[-1]^1]))


def test_random_capsules_item_is_generated_once_with_stable_id():
    from ..Items import ITEM_TABLE, RANDOM_CAPSULES, classification
    from ..world_constants import BASE_ID
    from BaseClasses import ItemClassification
    world = generate()
    assert ITEM_TABLE[RANDOM_CAPSULES] == BASE_ID + 35
    assert classification(RANDOM_CAPSULES) == ItemClassification.progression
    assert sum(item.name == RANDOM_CAPSULES for item in world.itempool) == 1


def test_full_refill_id_and_weighted_filler_distribution():
    from ..Items import ITEM_TABLE, FILLER_WEIGHTS
    assert ITEM_TABLE['Full Boost Refill'] == 847000036
    world = generate().worlds[1]
    from collections import Counter
    counts = Counter(world.get_filler_item_name() for _ in range(20000))
    for name, weight in FILLER_WEIGHTS.items():
        assert abs(counts[name] / 20000 - weight / 100) < .02


def test_complete_gecko_export_fits_native_table_budget():
    from ..client.capsule_refresh import gecko_ini
    lines = [line for line in gecko_ini().splitlines() if len(line)==17 and line[0] in '0123456789ABCDEF']
    assert len(lines)*8 <= 3256
