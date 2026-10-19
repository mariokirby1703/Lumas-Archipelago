"""Super Sonic bypasses story Act clear routes, never pickup or rank routes."""
from collections import Counter
from types import SimpleNamespace

import pytest

from ..Items import EMERALDS
from ..Rules import requirements, can_complete
from ..world_constants import STAGES, load_data
from . import generate


class State:
    def __init__(self, items):
        self.items = Counter(items)

    def has(self, name, player, count=1):
        return self.items[name] >= count

    def count(self, name, player):
        return self.items[name]


def test_super_sonic_only_bypasses_story_act_clears():
    manifest = load_data('logic_from_sheet_v2.json')
    # Deliberately require an absent Wisp for every route to isolate the bypass.
    import copy
    manifest = copy.deepcopy(manifest)
    blocked = {'status': 'documented', 'routes': [[{'ability': 'Cyan Laser'}]]}
    for row in manifest['locations'].values():
        row['normal'] = blocked
        row['movement'] = blocked
    world = SimpleNamespace(player=1, logic=manifest, options=SimpleNamespace(
        super_sonic=True, movement_unlocks=False, boost_lock=True, game_land_checks=True))
    state = State(EMERALDS)
    for stage in STAGES:
        mission = stage['mission_id']
        eligible = stage['kind'] == 'Act' and stage['zone_index'] < 7
        assert requirements(world, state, mission) == eligible
        if eligible:
            assert not requirements(world, state, mission, 'A')
        if stage['normal']:
            for index in range(1, 6):
                assert not requirements(world, state, f'{mission}:ring:{index}')
    for missing in EMERALDS:
        remaining = [e for e in EMERALDS if e != missing]
        assert not requirements(world, State(remaining * 7), 'stg310')
    world.options.super_sonic = False
    assert not requirements(world, state, 'stg310')


@pytest.mark.parametrize('movement', [False, True])
def test_super_sonic_unlocks_sequential_clear_routes_but_not_world_access(movement):
    multiworld = generate({'super_sonic': True, 'movement_unlocks': movement,
                           'starting_world': 0, 'world_progression': 0})
    world = multiworld.worlds[1]
    state = multiworld.state
    for emerald in EMERALDS:
        state.collect(world.create_item(emerald), prevent_sweep=True)
    for stage in STAGES:
        if stage['zone_index'] == 0 and stage['kind'] == 'Act':
            if not movement:
                assert can_complete(world, state, stage['mission_id'])
                assert world.get_location(stage['world'] + ' Act ' + str(stage['slot']) + ' - Clear').can_reach(state)
    assert not can_complete(world, state, 'stg310')


def test_movement_logic_never_gets_super_sonic_clear_bypass():
    multiworld = generate({'super_sonic': True, 'movement_unlocks': True, 'starting_world': 0})
    world = multiworld.worlds[1]
    for emerald in EMERALDS:
        multiworld.state.collect(world.create_item(emerald), prevent_sweep=True)
    from ..logic_v2 import check
    for stage in STAGES:
        mission = stage['mission_id']
        assert requirements(world, multiworld.state, mission) == check(world, multiworld.state, world.logic, mission)
