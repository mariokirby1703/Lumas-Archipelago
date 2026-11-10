import pytest

from .. import logic
from .test_logic_v3 import MANIFEST, State, world


def test_starlight_carnival_5_first_ring_needs_one_skydiving():
    key='stg320:ring:1'
    assert not logic.check(world(),State(),MANIFEST,key)
    assert logic.check(world(),State('Progressive Skydiving'),MANIFEST,key)
    assert logic.check(world(movement=False),State(),MANIFEST,key)


@pytest.mark.parametrize('key',['stg210','stg210:ring:4','stg210:ring:5'])
@pytest.mark.parametrize('base',[
    ('Progressive Crouch','Progressive Crouch'),('Progressive Yellow Drill Wisp',)])
@pytest.mark.parametrize('ability',['Double Jump','Stomp','Mid-Air Boost'])
def test_sweet_mountain_1_keeps_old_requirement_and_adds_aerial_alternatives(key,base,ability):
    assert not logic.check(world(),State(*base),MANIFEST,key)
    assert not logic.check(world(),State(ability),MANIFEST,key)
    assert logic.check(world(),State(*base,ability),MANIFEST,key)
    assert logic.check(world(movement=False),State(),MANIFEST,key)


@pytest.mark.parametrize('rank',['B','A','S','C',None])
def test_sweet_mountain_1_ranks_share_the_clear_requirement(rank):
    base=('White Boost Wisp','Cyan Laser Wisp','Progressive Yellow Drill Wisp')
    assert not logic.check(world(),State(*base),MANIFEST,'stg210',rank)
    assert logic.check(world(),State(*base,'Stomp'),MANIFEST,'stg210',rank)


@pytest.mark.parametrize('mission,alternatives',[
    ('stg140',('Progressive Yellow Drill Wisp','Homing Attack')),
    ('stg240',('Progressive Pink Spikes Wisp','Blue Cube Wisp')),
    ('stg250',('Blue Cube Wisp',)),
    ('stg610',('Purple Frenzy Wisp',)),
])
def test_b_rank_requirements_leave_clear_and_c_rank_unchanged(mission,alternatives):
    base=('Progressive Crouch','Progressive Crouch')
    if mission=='stg610':base+=('Homing Attack',)
    assert logic.check(world(),State(*base),MANIFEST,mission)
    assert logic.check(world(),State(*base),MANIFEST,mission,'C')
    assert not logic.check(world(),State(*base),MANIFEST,mission,'B')
    for ability in alternatives:
        assert logic.check(world(),State(*base,ability),MANIFEST,mission,'B')


def test_homing_attack_is_available_without_movement_locks():
    assert logic.check(world(movement=False),State(),MANIFEST,'stg140','B')
    for mission in ('stg240','stg250','stg610'):
        assert not logic.check(world(movement=False),State(),MANIFEST,mission,'B')


@pytest.mark.parametrize('movement',[False,True])
def test_updated_logic_can_generate_a_beatable_seed(movement):
    from . import generate
    multi=generate({'movement_unlocks':movement},seed=31102026,fill=True)
    assert multi.can_beat_game()


def test_starlight_6_requires_homing_even_with_hover_level_two():
    hover='Progressive Green Hover Wisp'
    assert not logic.check(world(),State(hover,hover),MANIFEST,'stg360')
    assert logic.check(world(),State(hover,'Homing Attack'),MANIFEST,'stg360')
    assert logic.check(world(movement=False),State('Green Hover Wisp'),MANIFEST,'stg360')


@pytest.mark.parametrize('mission,base',[
    ('stg510',('Progressive Yellow Drill Wisp',)),
    ('stg520',('Progressive Yellow Drill Wisp','Progressive Green Hover Wisp','Progressive Green Hover Wisp')),
])
def test_aquarium_clear_drill_routes_require_two_breathing_items(mission,base):
    assert not logic.check(world(),State(*base,'Progressive Breathing'),MANIFEST,mission)
    assert logic.check(world(),State(*base,'Progressive Breathing','Progressive Breathing'),MANIFEST,mission)
    assert logic.check(world(movement=False),State('Green Hover Wisp'),MANIFEST,mission)


@pytest.mark.parametrize('key,items,unlock',[
    ('stg320:ring:1',(),('Progressive Skydiving',)),
    ('stg420:ring:1',('Progressive Rail',),('Progressive Skydiving',)),
    ('stg610:one_up',('Homing Attack',),('Progressive Stunts',)*3),
    ('stg330:ring:5',('Progressive Pink Spikes Wisp',),('Progressive Pink Spikes Wisp',)),
    ('stg540:ring:1',(),('Blue Cube Wisp',)),
    ('stg660:one_up',('Cyan Laser Wisp',),('Wall Jump',)),
])
def test_restart_routes_are_advanced_and_do_not_unlock_seed_locations(key,items,unlock):
    assert not logic.check(world(),State(*items),MANIFEST,key)
    assert logic.matches(world(),State(*items),MANIFEST['locations'][key]['advanced_movement'])
    assert logic.check(world(),State(*items,*unlock),MANIFEST,key)


def test_stunts_one_and_two_do_not_make_asteroid_one_up_safe():
    for count in (1,2):
        assert not logic.check(world(),State('Homing Attack',*('Progressive Stunts',)*count),
                               MANIFEST,'stg610:one_up')


def test_aquarium_two_first_ring_also_needs_cube_without_ability_locks():
    assert not logic.check(world(movement=False),State(),MANIFEST,'stg540:ring:1')
    assert logic.check(world(movement=False),State('Blue Cube Wisp'),MANIFEST,'stg540:ring:1')


def test_starlight_four_b_rank_requires_frenzy_but_clear_and_c_do_not():
    for movement in (False,True):
        w=world(movement=movement)
        assert logic.check(w,State(),MANIFEST,'stg350')
        assert logic.check(w,State(),MANIFEST,'stg350','C')
        assert not logic.check(w,State(),MANIFEST,'stg350','B')
        assert logic.check(w,State('Purple Frenzy Wisp'),MANIFEST,'stg350','B')


@pytest.mark.parametrize('key', ['stg510:ring:2', 'stg510:ring:3', 'stg510:ring:5', 'stg510:one_up'])
def test_aquarium_one_drill_pickups_require_breathing_two(key):
    items = ('Progressive Yellow Drill Wisp',)
    assert not logic.check(world(), State(*items, 'Progressive Breathing'), MANIFEST, key)
    assert logic.check(world(), State(*items, 'Progressive Breathing', 'Progressive Breathing'), MANIFEST, key)


def test_all_aquarium_one_breathing_routes_require_at_least_two():
    for key, entry in MANIFEST['locations'].items():
        if key.split(':', 1)[0] != 'stg510':
            continue
        for mode in ('normal', 'movement', 'advanced_normal', 'advanced_movement'):
            for route in entry[mode]:
                for token in route:
                    name, count = logic.token_parts(token)
                    if name == 'breathing':
                        assert count >= 2, (key, mode, route)
