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
from ..Items import (BARKER_COIN, COIN_BUNDLE_DATA, COIN_TRAP_DATA, GOAL_WORLD_ACCESS,
                     PAR_CLUB_PIECES, UNLOCKS)
from ..Locations import BARKER_REQUIREMENT_LOCATION, LOCATION_TABLE
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
        self.assertGreater(samples[50] + samples[100], 4500)

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

    def test_trap_weight_can_disable_or_fill_with_traps(self):
        disabled = generate({'goal': 1, 'trap_weight': 0}, seed=101).worlds[1]
        enabled = generate({'goal': 1, 'trap_weight': 100}, seed=102).worlds[1]
        self.assertFalse(any(disabled.get_filler_item_name() in COIN_TRAP_DATA for _ in range(1000)))
        self.assertTrue(all(enabled.get_filler_item_name() in COIN_TRAP_DATA for _ in range(1000)))

    def test_data_and_shop_tiers(self):
        self.assertEqual(len(LOCATION_TABLE), 215)
        self.assertEqual(len({d.code for d in LOCATION_TABLE.values()}), 215)
        self.assertEqual(len(PRIZES), 88)
        self.assertEqual(len(HOLES), 27)
        for world in range(9):
            purchases = sorted((p for p in PRIZES if p['kind'] == 'shop' and p['world'] == world),
                               key=lambda p: (p['price'], p['id']))
            self.assertEqual([p['pieces'] for p in purchases], [0, 0, 1, 1, 2, 2, 3])

    def test_each_start_and_goals(self):
        for start in range(9):
            for goal, access in ((0, 0), (1, 0), (1, 1), (2, 0)):
                with self.subTest(start=start, goal=goal, access=access):
                    final = (start + 1) % 9
                    mw = generate({'starting_world': start, 'goal': goal, 'goal_world': final,
                                   'goal_world_access': access}, start*10+goal+access, fill=True)
                    world = mw.worlds[1]
                    self.assertEqual(world.starting_world, start)
                    self.assertEqual(len(mw.get_unfilled_locations()), 0)
                    self.assertTrue(mw.can_beat_game())
                    if goal == 1:
                        self.assertEqual(world.goal_world, final)
                        self.assertNotIn(UNLOCKS[final], [item.name for item in mw.itempool])
                        if access:
                            self.assertEqual(world.get_location(BARKER_REQUIREMENT_LOCATION).item.name,
                                             GOAL_WORLD_ACCESS)
                        else:
                            self.assertIn(GOAL_WORLD_ACCESS, [item.name for item in mw.itempool])
                    if goal == 2 or access:
                        self.assertFalse(world.options.barker_shop_checks)
                        self.assertFalse(any(LOCATION_TABLE[n].kind == 'barker_shop' for n in world.active_locations))

    def test_disabled_families_and_perfect_only(self):
        minimal = dict(barker_coin_checks=0, world_secrets=0, shop_checks=0,
                       barker_shop_checks=0, minigame_checks=0)
        mw = generate(minimal, fill=True)
        self.assertEqual(len(mw.get_locations()), 54)
        self.assertTrue(mw.can_beat_game())
        for mode, count in ((0, 0), (1, 9), (2, 9), (3, 18)):
            world = generate({**minimal, 'minigame_checks': mode}).worlds[1]
            self.assertEqual(len(world.active_locations), 54+count)
            if mode == 2:
                self.assertFalse(any(LOCATION_TABLE[n].kind == 'win' for n in world.active_locations))

    def test_invalid_options(self):
        corrected = generate(dict(starting_world=1, goal=1, goal_world=1)).worlds[1]
        self.assertNotEqual(corrected.starting_world, corrected.goal_world)
        minimal_hunt = generate(dict(goal=2, barker_coin_checks=0, world_secrets=0, shop_checks=0,
                                      barker_shop_checks=0, minigame_checks=0), fill=True)
        self.assertTrue(minimal_hunt.can_beat_game())

    def test_par_pieces_exist_only_for_shop_progression(self):
        enabled = generate({'shop_checks': 1}).worlds[1]
        counts = Counter(item.name for item in enabled.multiworld.itempool)
        self.assertTrue(all(counts[name] == 3 for name in PAR_CLUB_PIECES))
        self.assertTrue(all(enabled.create_item(name).advancement for name in PAR_CLUB_PIECES))
        disabled = generate({'shop_checks': 0}).worlds[1]
        self.assertFalse(any(item.name in PAR_CLUB_PIECES for item in disabled.multiworld.itempool))

    def test_shop_logic_uses_received_piece_items(self):
        mw = generate({'starting_world': 0, 'shop_checks': 1})
        world = mw.worlds[1]
        purchases = sorted((p for p in PRIZES if p['kind'] == 'shop' and p['world'] == 0),
                           key=lambda p: (p['price'], p['id']))
        purchase_names = [f"{WORLDS[0]} Shop: {p['name']}" for p in purchases]
        club = next(p for p in PRIZES if p['kind'] == 'club' and p['world'] == 0)
        club_name = f"{WORLDS[0]} - Par Club Reward: {club['name']}"
        state = CollectionState(mw)
        for piece_count, reachable_count in enumerate((2, 4, 6, 7)):
            self.assertEqual(sum(state.can_reach(name, 'Location', 1) for name in purchase_names),
                             reachable_count)
            self.assertEqual(state.can_reach(club_name, 'Location', 1), piece_count == 3)
            if piece_count < 3:
                state.collect(world.create_item(PAR_CLUB_PIECES[0]), prevent_sweep=True)

    def test_names_and_barker_pool_size(self):
        self.assertEqual(PAR_CLUB_PIECES[2], "Amazeon Par Club Piece")
        self.assertIn("Amazeon Shop: Jub Jub Ball", LOCATION_TABLE)
        self.assertFalse(any("Purchase" in name for name in LOCATION_TABLE))
        for required, expected in ((1, 2), (5, 8), (27, 41), (50, 75)):
            with self.subTest(required=required):
                world = generate({'goal': 2, 'barker_coins_required': required}).worlds[1]
                self.assertEqual(sum(item.name == BARKER_COIN for item in world.multiworld.itempool), expected)
                self.assertEqual(world.required_coins, required)
                self.assertEqual(world.total_barker_coins, expected)

    def test_random_options_multiworld_and_output(self):
        rng = random.Random(456)
        for seed in range(30):
            options = {name: rng.randrange(2) for name in ('hole_in_one_checks', 'world_secrets',
                       'shop_checks', 'barker_shop_checks', 'goal_world_access')}
            options['goal'] = rng.randrange(3)
            options['starting_world'] = rng.randrange(9)
            options['goal_world'] = (options['starting_world'] + rng.randrange(1, 9)) % 9
            options['barker_coins_required'] = rng.randrange(1, 51)
            options['trap_weight'] = rng.randrange(101)
            options['minigame_checks'] = rng.randrange(4)
            mw = generate(options, seed, players=2 if seed % 5 == 0 else 1, fill=True)
            self.assertTrue(mw.can_beat_game(), (seed, options))
            self.assertFalse(mw.get_unfilled_locations())
        with tempfile.TemporaryDirectory() as tmp:
            mw.worlds[1].generate_output(tmp)
            data = json.loads(next(Path(tmp).glob('*.apcgm')).read_text())
            self.assertEqual(data['slot_data'], mw.worlds[1].fill_slot_data())
