import json
import random
import tempfile
import unittest
from collections import Counter
from argparse import Namespace
from pathlib import Path

from BaseClasses import CollectionState, MultiWorld
from Fill import distribute_items_restrictive
from test.general import gen_steps
from worlds.AutoWorld import call_all

from ..data import HOLES, PRIZES, WORLDS
from ..Items import BARKER_COIN, COIN_BUNDLE_DATA, COIN_TRAP_DATA, UNLOCKS
from ..Locations import LOCATION_TABLE
from ..world import CarnivalGamesMiniGolfWorld
from . import MiniGolfTestBase


def generate(options=None, seed=0, players=1, fill=False):
    multiworld = MultiWorld(players)
    multiworld.set_seed(seed)
    multiworld.seed_name = f"MiniGolfTest{seed}"
    multiworld.player_name = {}
    args = Namespace()
    for player in multiworld.player_ids:
        multiworld.game[player] = CarnivalGamesMiniGolfWorld.game
        multiworld.player_name[player] = f"Golfer{player}"
    for name, option in CarnivalGamesMiniGolfWorld.options_dataclass.type_hints.items():
        setattr(args, name, {p: option.from_any((options or {}).get(name, option.default))
                             for p in multiworld.player_ids})
    multiworld.set_options(args)
    multiworld.state = CollectionState(multiworld)
    for step in gen_steps:
        call_all(multiworld, step)
    if fill:
        distribute_items_restrictive(multiworld)
    return multiworld


class TestDefault(MiniGolfTestBase):
    run_default_tests = True

    def test_starter(self):
        self.assertTrue(self.can_reach_region(WORLDS[self.world.starting_world]))
        self.assertNotIn(UNLOCKS[self.world.starting_world], [i.name for i in self.multiworld.itempool])


class TestWorldData(unittest.TestCase):
    def test_bundle_frequency(self):
        world = generate({'goal': 1}, seed=20260914).worlds[1]
        generated = (world.get_filler_item_name() for _ in range(10000))
        samples = Counter(COIN_BUNDLE_DATA[name][1] for name in generated if name in COIN_BUNDLE_DATA)
        self.assertTrue(samples[5] < samples[10] < samples[500] < samples[200] < samples[20])
        self.assertGreater(samples[50], samples[20])
        self.assertGreater(samples[100], samples[20])
        self.assertGreater(samples[50] + samples[100], 5000)

    def test_traps_are_classified_and_weighted(self):
        world = generate({'goal': 1}, seed=20260915).worlds[1]
        samples = Counter()
        traps = 0
        for _ in range(20000):
            item = world.create_item(world.get_filler_item_name())
            if item.name in COIN_TRAP_DATA:
                traps += 1
                samples[COIN_TRAP_DATA[item.name][1]] += 1
                self.assertTrue(item.trap)
        self.assertTrue(1700 < traps < 2300)
        self.assertTrue(samples[50] < samples[20] < samples[10] < samples[5])

    def test_data_and_shop_tiers(self):
        self.assertEqual(len(LOCATION_TABLE), 187)
        self.assertEqual(len({d.code for d in LOCATION_TABLE.values()}), 187)
        self.assertEqual(len(PRIZES), 88)
        self.assertEqual(len(HOLES), 27)
        for world in range(9):
            purchases = sorted((p for p in PRIZES if p['kind'] == 'shop' and p['world'] == world),
                               key=lambda p: (p['price'], p['id']))
            self.assertEqual([p['pieces'] for p in purchases], [0, 0, 1, 1, 2, 2, 3])

    def test_each_start_and_goals(self):
        for start in range(1, 10):
            for goal, gated in ((0, 0), (1, 0), (0, 1), (1, 1)):
                with self.subTest(start=start, goal=goal, gated=gated):
                    mw = generate({'starting_world': start, 'goal': goal,
                                   'barker_goal_world_requirement': gated}, start*10+goal+gated, fill=True)
                    world = mw.worlds[1]
                    self.assertEqual(world.starting_world, start-1)
                    self.assertEqual(len(mw.get_unfilled_locations()), 0)
                    self.assertTrue(mw.can_beat_game())
                    if gated:
                        self.assertNotEqual(world.starting_world, world.goal_world)
                        self.assertFalse(mw.state.can_reach(WORLDS[world.goal_world], 'Region', 1))
                        for _ in range(world.required_coins-1):
                            mw.state.collect(world.create_item(BARKER_COIN), prevent_sweep=True)
                        self.assertFalse(mw.state.can_reach(WORLDS[world.goal_world], 'Region', 1))
                        mw.state.collect(world.create_item(BARKER_COIN), prevent_sweep=True)
                        self.assertTrue(mw.state.can_reach(WORLDS[world.goal_world], 'Region', 1))
                    if goal or gated:
                        self.assertFalse(world.options.barker_shop_checks)
                        self.assertFalse(any(LOCATION_TABLE[n].kind == 'barker_shop' for n in world.active_locations))

    def test_disabled_families_and_perfect_only(self):
        minimal = dict(barker_coin_checks=0, world_secrets=0, shop_checks=0,
                       barker_shop_checks=0, minigame_checks=0)
        mw = generate(minimal, fill=True)
        self.assertEqual(len(mw.get_locations()), 27)
        self.assertTrue(mw.can_beat_game())
        for mode, count in ((0, 0), (1, 9), (2, 9), (3, 18)):
            world = generate({**minimal, 'minigame_checks': mode}).worlds[1]
            self.assertEqual(len(world.active_locations), 27+count)
            if mode == 2:
                self.assertFalse(any(LOCATION_TABLE[n].kind == 'win' for n in world.active_locations))

    def test_invalid_options(self):
        with self.assertRaisesRegex(ValueError, 'must differ'):
            generate(dict(starting_world=1, goal_world=1, barker_goal_world_requirement=1))
        with self.assertRaisesRegex(ValueError, 'Too few'):
            generate(dict(goal=1, barker_coin_checks=0, world_secrets=0, shop_checks=0,
                          barker_shop_checks=0, minigame_checks=0))

    def test_random_options_multiworld_and_output(self):
        rng = random.Random(456)
        for seed in range(30):
            options = {name: rng.randrange(2) for name in ('goal', 'hole_in_one_checks', 'world_secrets',
                       'shop_checks', 'barker_shop_checks', 'barker_goal_world_requirement')}
            options['barker_coins_required'] = rng.randrange(1, 28)
            options['minigame_checks'] = rng.randrange(4)
            mw = generate(options, seed, players=2 if seed % 5 == 0 else 1, fill=True)
            self.assertTrue(mw.can_beat_game(), (seed, options))
            self.assertFalse(mw.get_unfilled_locations())
        with tempfile.TemporaryDirectory() as tmp:
            mw.worlds[1].generate_output(tmp)
            data = json.loads(next(Path(tmp).glob('*.apcgm')).read_text())
            self.assertEqual(data['slot_data'], mw.worlds[1].fill_slot_data())
