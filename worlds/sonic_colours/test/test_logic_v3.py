"""Regression tests for completed NL/ML logic and spreadsheet corrections."""
from collections import Counter
from types import SimpleNamespace
import itertools
import pytest
from ..world_constants import load_data
from .. import logic as logic
from . import generate

MANIFEST = load_data('logic_from_sheet_v3.json')


class State:
    def __init__(self, *items):
        self.items = Counter(items)

    def has(self, name, player, count=1):
        return self.items[name] >= count

    def count(self, name, player):
        return self.items[name]


def world(*, movement=True, boost=True, land=True):
    return SimpleNamespace(player=1, options=SimpleNamespace(
        movement_unlocks=movement, boost_lock=boost, game_land_checks=land))


def test_v3_manifest_complete_and_route_tokens_real():
    assert logic.validate_manifest(MANIFEST) is MANIFEST
    assert len(MANIFEST['locations']) == 298
    assert MANIFEST['unresolved_routes'] == {}


def test_aquarium_park_1_red_ring_4_exactly_four_alternative_routes():
    routes = MANIFEST['locations']['stg510:ring:4']['movement']
    assert len(routes) == 4
    assert routes == [
        ['boost','laser','crouch:2','stomp'],
        ['breathing','swim','laser','crouch:2','stomp'],
        ['breathing','drill','laser','crouch:2'],
        ['breathing:2','swim','laser','crouch:2'],
    ]
    inventories = (
        ('White Boost Wisp','Cyan Laser Wisp','Progressive Crouch','Progressive Crouch','Stomp'),
        ('Progressive Breathing','Swim','Cyan Laser Wisp','Progressive Crouch','Progressive Crouch','Stomp'),
        ('Progressive Breathing','Progressive Yellow Drill Wisp','Cyan Laser Wisp','Progressive Crouch','Progressive Crouch'),
        ('Progressive Breathing','Progressive Breathing','Swim','Cyan Laser Wisp','Progressive Crouch','Progressive Crouch'),
    )
    for inv in inventories:
        assert logic.check(world(), State(*inv), MANIFEST, 'stg510:ring:4')
    assert not logic.check(world(), State('Cyan Laser Wisp'), MANIFEST, 'stg510:ring:4')


def test_game_land_7_3_clear_and_heart_require_random_capsules():
    routes = [['breathing','drill','random_capsules'],
              ['breathing:3','rocket','random_capsules']]
    for key in ('stgC10', 'stgC10:eggman_heart'):
        assert MANIFEST['locations'][key]['movement'] == routes
        owned = ('Progressive Breathing','Progressive Yellow Drill Wisp')
        assert not logic.check(world(), State(*owned), MANIFEST, key)
        assert logic.check(world(), State(*owned, 'Random Capsules'), MANIFEST, key)
        owned = ('Progressive Breathing',)*3 + ('Orange Rocket Wisp',)
        assert not logic.check(world(), State(*owned), MANIFEST, key)
        assert logic.check(world(), State(*owned, 'Random Capsules'), MANIFEST, key)


def test_stage_wisp_requirements_are_mandatory_for_s_and_a_not_b_c():
    w = world(movement=False)
    assert logic.check(w, State(), MANIFEST, 'stg110')
    assert logic.check(w, State(), MANIFEST, 'stg110', 'B')
    assert logic.check(w, State(), MANIFEST, 'stg110', 'C')
    for rank in ('S', 'A'):
        assert not logic.check(w, State(), MANIFEST, 'stg110', rank)
        assert not logic.check(w, State('White Boost Wisp','Cyan Laser Wisp'), MANIFEST, 'stg110', rank)
        assert logic.check(w, State('White Boost Wisp','Cyan Laser Wisp',
                                    'Yellow Drill Wisp'), MANIFEST, 'stg110', rank)


def test_s_rank_extra_movement_applies_only_with_ability_locks():
    assert MANIFEST['rank_s_extra_movement']['stg340'] == [['stomp']]
    assert not logic.check(world(), State(), MANIFEST, 'stg340', 'S')
    assert logic.check(world(), State('Stomp'), MANIFEST, 'stg340', 'S')
    assert logic.check(world(movement=False), State(), MANIFEST, 'stg340', 'S')


def test_random_capsules_is_progression_for_movement_game_land():
    from BaseClasses import ItemClassification
    game = generate({'game_land_checks': 1, 'movement_unlocks': 1, 'wisp_capsules': 0}).worlds[1]
    assert game.create_item('Random Capsules').classification == ItemClassification.progression
    game2 = generate({'game_land_checks': 1, 'movement_unlocks': 0, 'wisp_capsules': 0}).worlds[1]
    assert game2.create_item('Random Capsules').classification == ItemClassification.useful


@pytest.mark.parametrize('movement,boost', itertools.product((False,True), repeat=2))
def test_all_completed_main_routes_reachable_with_full_available_items(movement,boost):
    from ..Items import MOVEMENT_POOL
    from ..wisps import required_wisp_items
    w = world(movement=movement, boost=boost)
    owned = State(*required_wisp_items(w.options),
                  *(['Progressive Yellow Drill Wisp','Progressive Green Hover Wisp',
                     'Progressive Pink Spikes Wisp'] if movement else []),
                  *MOVEMENT_POOL, *('Progressive Game Land Speed',)*4,
                  'Random Capsules')
    for key in MANIFEST['locations']:
        assert logic.check(w, owned, MANIFEST, key), key
    for mission in MANIFEST['rank_wisps']:
        for rank in ('A','S'):
            assert logic.check(w, owned, MANIFEST, mission, rank), (mission, rank)
