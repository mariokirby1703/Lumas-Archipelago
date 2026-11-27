import pytest

from ..Items import NORMAL_WISP_ITEMS, ITEM_TABLE
from ..world import SonicColoursWorld
from .. import logic
from . import generate
from .test_logic_v3 import MANIFEST, State, world


@pytest.mark.parametrize('name', NORMAL_WISP_ITEMS)
@pytest.mark.parametrize('movement', [False, True])
def test_wisp_hint_alias_matches_the_item_in_either_pool(name, movement):
    multiworld = generate({'movement_unlocks': movement})
    alias = SonicColoursWorld.item_name_groups[name]
    assert alias == {name, 'Progressive '+name}
    assert alias <= ITEM_TABLE.keys()
    present = {item.name for item in multiworld.itempool if item.player == 1}
    assert alias & present == {('Progressive ' if movement else '')+name}
    assert multiworld.worlds[1].get_data_package_data()['item_name_groups'][name] == sorted(alias)


def test_game_land_two_one_heart_speed_route_requires_level_three():
    key = 'stgD20:eggman_heart'
    speed = 'Progressive Game Land Speed'
    assert not logic.check(world(), State(speed), MANIFEST, key)
    assert logic.check(world(), State(speed, speed), MANIFEST, key)
    assert logic.check(world(), State('Double Jump'), MANIFEST, key)
    assert logic.check(world(), State('Mid-Air Boost'), MANIFEST, key)
    assert logic.check(world(movement=False), State(), MANIFEST, key)


@pytest.mark.parametrize('alias,item', [
    ('Game Land Speed', 'Progressive Game Land Speed'),
    ('Crouch', 'Progressive Crouch'),
    ('Slide', 'Progressive Crouch'),
    ('Sliding', 'Progressive Crouch'),
])
def test_progressive_movement_hint_aliases(alias, item):
    assert SonicColoursWorld.item_name_groups[alias] == {item}
    assert item in ITEM_TABLE
    assert SonicColoursWorld.get_data_package_data()['item_name_groups'][alias] == [item]
