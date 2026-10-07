import json
import random
import tempfile
import unittest
from collections import Counter
from argparse import Namespace
from pathlib import Path

from BaseClasses import CollectionState, ItemClassification, MultiWorld
from Fill import distribute_items_restrictive
from test.general import gen_steps
from worlds.AutoWorld import call_all

from ..data import HOLES, PRIZES, WORLDS
from ..Items import (BARKER_COIN, COIN_BUNDLE_DATA, COIN_TRAP_DATA, PAR_CLUB_PIECES, UNLOCKS,
                     coin_bundle_name)
from ..Locations import BARKER_REQUIREMENT_LOCATION, HIO_IMPOSSIBLE, HIO_POSSIBLE, LOCATION_TABLE
from ..world import CarnivalGamesMiniGolfWorld
from . import MiniGolfTestBase


def generate(options=None, seed=0, players=1, fill=False, passthrough=None):
    multiworld = MultiWorld(players)
    multiworld.set_seed(seed)
    if passthrough is not None:
        multiworld.re_gen_passthrough = {CarnivalGamesMiniGolfWorld.game: passthrough}
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
        self.assertEqual(samples[100] + samples[200] + samples[500], 0)
        self.assertTrue(samples[5] < samples[10] < samples[20] < samples[50])
        self.assertGreater(samples[50], 4500)

    def test_bounded_high_value_bundles_fit_minimal_pool(self):
        minimal = dict(minigame_checks=0, hole_in_one_checks=0, barker_coin_checks=0,
                       world_secrets=0, shop_checks=0, barker_shop_checks=0)
        world = generate(minimal, fill=True).worlds[1]
        pool = world.multiworld.itempool
        for index in range(len(WORLDS)):
            bundles = [item for item in pool if item.name == coin_bundle_name(index, 500)]
            self.assertEqual(len(bundles), 2)
            self.assertTrue(all(item.classification == ItemClassification.progression for item in bundles))
        for amount in (100, 200):
            bundles = [item for item in pool
                       if item.name in COIN_BUNDLE_DATA and COIN_BUNDLE_DATA[item.name][1] == amount]
            self.assertEqual(len(bundles), 5)
            self.assertEqual(len({COIN_BUNDLE_DATA[item.name][0] for item in bundles}), 5)
            self.assertTrue(all(item.classification == ItemClassification.useful for item in bundles))
        self.assertEqual(len(world.multiworld.get_locations()), 54)
        self.assertTrue(world.multiworld.can_beat_game())

    def test_smaller_bundles_remain_filler(self):
        world = generate().worlds[1]
        for amount in (5, 10, 20, 50):
            self.assertEqual(world.create_item(coin_bundle_name(0, amount)).classification,
                             ItemClassification.filler)

    def test_traps_are_classified_and_weighted(self):
        world = generate({'goal': 1, 'trap_weight': 10}, seed=20260915).worlds[1]
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
        self.assertEqual(generate().worlds[1].options.trap_weight.value, 10)
        disabled = generate({'goal': 1, 'trap_weight': 0}, seed=101).worlds[1]
        enabled = generate({'goal': 1, 'trap_weight': 100}, seed=102).worlds[1]
        self.assertFalse(any(disabled.get_filler_item_name() in COIN_TRAP_DATA for _ in range(1000)))
        self.assertTrue(all(enabled.get_filler_item_name() in COIN_TRAP_DATA for _ in range(1000)))

    def test_data_and_shop_tiers(self):
        self.assertEqual(len(LOCATION_TABLE), 208)
        self.assertEqual(len({d.code for d in LOCATION_TABLE.values()}), 208)
        self.assertEqual(len(PRIZES), 88)
        self.assertEqual(len(HOLES), 27)
        for world in range(9):
            purchases = sorted((p for p in PRIZES if p['kind'] == 'shop' and p['world'] == world),
                               key=lambda p: (p['price'], p['id']))
            self.assertEqual([p['pieces'] for p in purchases], [0, 0, 1, 1, 2, 2, 3])

    def test_hio_feasibility_allowlist(self):
        self.assertEqual(HIO_IMPOSSIBLE, {0, 1, 4, 7, 10, 15, 22, 25})
        self.assertEqual(len(HIO_POSSIBLE), 19)
        self.assertEqual({d.index for d in LOCATION_TABLE.values() if d.kind == 'hio'}, set(HIO_POSSIBLE))

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
                        if access:
                            self.assertEqual(world.get_location(BARKER_REQUIREMENT_LOCATION).item.name,
                                             UNLOCKS[final])
                        else:
                            self.assertIn(UNLOCKS[final], [item.name for item in mw.itempool])
                    if goal == 2 or access:
                        self.assertFalse(world.options.barker_shop_checks)
                        self.assertFalse(any(LOCATION_TABLE[n].kind == 'barker_shop' for n in world.active_locations))

    def test_disabled_families_and_perfect_only(self):
        minimal = dict(barker_coin_checks=0, world_secrets=0, shop_checks=0,
                       barker_shop_checks=0, minigame_checks=0)
        mw = generate(minimal, fill=True)
        self.assertEqual(len(mw.get_locations()), 54)
        self.assertTrue(mw.can_beat_game())
        for mode, count in ((0, 0), (1, 10), (2, 9), (3, 19)):
            world = generate({**minimal, 'minigame_checks': mode}).worlds[1]
            self.assertEqual(len(world.active_locations), 54+count)
            if mode == 2:
                self.assertFalse(any(LOCATION_TABLE[n].kind == 'win' for n in world.active_locations))

    def test_spider_subgame_has_only_supported_option_locations(self):
        name = "Devil's Brew - Spiders - Win"
        self.assertIn(name, LOCATION_TABLE)
        self.assertNotIn("Devil's Brew - Spiders - Perfect", LOCATION_TABLE)
        self.assertNotIn(name, generate({'minigame_checks': 0}).worlds[1].active_locations)
        self.assertIn(name, generate({'minigame_checks': 1}).worlds[1].active_locations)
        self.assertNotIn(name, generate({'minigame_checks': 2}).worlds[1].active_locations)
        self.assertIn(name, generate({'minigame_checks': 3}).worlds[1].active_locations)

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

    def test_shop_logic_allows_early_tiers_via_access_or_coin_bundles(self):
        mw = generate({'starting_world': 0, 'shop_checks': 1})
        world = mw.worlds[1]
        shop_world = 1
        purchases = sorted((p for p in PRIZES if p['kind'] == 'shop' and p['world'] == shop_world),
                           key=lambda p: (p['price'], p['id']))
        purchase_names = [f"{WORLDS[shop_world]} Shop: {p['name']}" for p in purchases]
        club = next(p for p in PRIZES if p['kind'] == 'club' and p['world'] == shop_world)
        club_name = f"{WORLDS[shop_world]} - Par Club Reward: {club['name']}"
        state = CollectionState(mw)
        self.assertEqual(sum(state.can_reach(name, 'Location', 1) for name in purchase_names), 0)
        state.collect(world.create_item(coin_bundle_name(shop_world, 500)), prevent_sweep=True)
        self.assertEqual(sum(state.can_reach(name, 'Location', 1) for name in purchase_names), 2)
        state.collect(world.create_item(coin_bundle_name(shop_world, 500)), prevent_sweep=True)
        self.assertEqual(sum(state.can_reach(name, 'Location', 1) for name in purchase_names), 2)
        state.collect(world.create_item(PAR_CLUB_PIECES[shop_world]), prevent_sweep=True)
        self.assertEqual(sum(state.can_reach(name, 'Location', 1) for name in purchase_names), 4)
        state.collect(world.create_item(PAR_CLUB_PIECES[shop_world]), prevent_sweep=True)
        self.assertEqual(sum(state.can_reach(name, 'Location', 1) for name in purchase_names), 4)
        self.assertFalse(state.can_reach(club_name, 'Location', 1))
        state.collect(world.create_item(PAR_CLUB_PIECES[shop_world]), prevent_sweep=True)
        self.assertEqual(sum(state.can_reach(name, 'Location', 1) for name in purchase_names), 4)
        self.assertFalse(state.can_reach(club_name, 'Location', 1))
        state.collect(world.create_item(UNLOCKS[shop_world]), prevent_sweep=True)
        self.assertEqual(sum(state.can_reach(name, 'Location', 1) for name in purchase_names), 7)
        self.assertTrue(state.can_reach(club_name, 'Location', 1))

    def test_names_and_barker_pool_size(self):
        self.assertEqual(UNLOCKS, tuple(f"{world} Access" for world in WORLDS))
        self.assertEqual(PAR_CLUB_PIECES[2], "Amazeon Par Club Piece")
        self.assertIn("Amazeon Shop: Jub Jub Ball", LOCATION_TABLE)
        self.assertFalse(any("Purchase" in name for name in LOCATION_TABLE))
        self.assertIn("50 Amazeon Coins", COIN_BUNDLE_DATA)
        self.assertIn("-10 Fairytella Coins", COIN_TRAP_DATA)
        for required, expected in ((1, 2), (5, 8), (27, 41), (40, 60)):
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
            options['barker_coins_required'] = rng.randrange(1, 41)
            options['trap_weight'] = rng.randrange(101)
            options['minigame_checks'] = rng.randrange(4)
            mw = generate(options, seed, players=2 if seed % 5 == 0 else 1, fill=True)
            self.assertTrue(mw.can_beat_game(), (seed, options))
            self.assertFalse(mw.get_unfilled_locations())
        with tempfile.TemporaryDirectory() as tmp:
            mw.worlds[1].generate_output(tmp)
            data = json.loads(next(Path(tmp).glob('*.apcgm')).read_text())
            self.assertEqual(data['slot_data'], mw.worlds[1].fill_slot_data())

    def test_surplus_barker_coins_are_useful_and_fit_small_pool(self):
        from BaseClasses import ItemClassification
        from ..client.runtime import validate_slot
        options = dict(goal=2, barker_coins_required=40, minigame_checks=0,
                       barker_coin_checks=0, world_secrets=0, shop_checks=0,
                       barker_shop_checks=0, hole_in_one_checks=0)
        mw = generate(options, fill=True)
        world = mw.worlds[1]
        coins = [location.item for location in mw.get_filled_locations() if location.item.name == BARKER_COIN]
        self.assertEqual(sum(item.classification == ItemClassification.progression for item in coins), 40)
        self.assertEqual(sum(item.classification == ItemClassification.useful for item in coins), 0)
        self.assertEqual(len(mw.get_filled_locations()), 54)
        self.assertTrue(mw.can_beat_game())
        validate_slot(world.fill_slot_data())

    def test_maximum_barker_requirement_fits_with_only_mandatory_checks(self):
        minimal = dict(barker_coins_required=40, minigame_checks=0, hole_in_one_checks=0,
                       barker_coin_checks=0, world_secrets=0, shop_checks=0, barker_shop_checks=0)
        hunt = generate({**minimal, 'goal': 2}, fill=True)
        self.assertEqual(len(hunt.get_locations()), 54)
        self.assertTrue(hunt.can_beat_game())
        self.assertEqual(sum(item.name == BARKER_COIN for item in hunt.itempool), 40)
        self.assertEqual(sum(location.item.name in UNLOCKS for location in hunt.get_filled_locations()), 8)

        goal_world = generate({**minimal, 'goal': 1, 'starting_world': 0, 'goal_world': 1,
                               'goal_world_access': 1}, fill=True)
        self.assertEqual(len(goal_world.get_locations()), 55)
        self.assertTrue(goal_world.can_beat_game())
        self.assertEqual(sum(item.name == BARKER_COIN for item in goal_world.itempool), 40)
        self.assertEqual(sum(location.item.name in UNLOCKS for location in goal_world.get_filled_locations()), 8)
        self.assertEqual(goal_world.worlds[1].get_location(BARKER_REQUIREMENT_LOCATION).item.name,
                         UNLOCKS[1])

    def test_universal_tracker_regeneration_restores_resolved_logic(self):
        cases = (
            dict(starting_world=0, goal=1, goal_world=1, goal_world_access=0,
                 barker_coins_required=1, minigame_checks=0, hole_in_one_checks=0,
                 barker_coin_checks=0, world_secrets=0, shop_checks=0, barker_shop_checks=0),
            dict(starting_world=2, goal=1, goal_world=1, goal_world_access=1,
                 barker_coins_required=40, minigame_checks=3, hole_in_one_checks=1,
                 barker_coin_checks=1, world_secrets=0, shop_checks=1, barker_shop_checks=1),
            # Initial generation must resolve this collision once; regeneration must reuse it.
            dict(starting_world=4, goal=1, goal_world=4, goal_world_access=1,
                 barker_coins_required=5, minigame_checks=2, hole_in_one_checks=1,
                 barker_coin_checks=0, world_secrets=1, shop_checks=0, barker_shop_checks=1),
            dict(starting_world=8, goal=2, goal_world=3, goal_world_access=0,
                 barker_coins_required=27, minigame_checks=1, hole_in_one_checks=0,
                 barker_coin_checks=1, world_secrets=1, shop_checks=0, barker_shop_checks=1),
        )
        for seed, options in enumerate(cases, 800):
            with self.subTest(seed=seed, options=options):
                original = generate(options, seed).worlds[1]
                slot_data = original.fill_slot_data()
                interpreted = original.interpret_slot_data(slot_data)
                regenerated = generate(options, seed + 10000, passthrough=interpreted).worlds[1]
                self.assertEqual(regenerated.starting_world, original.starting_world)
                self.assertEqual(regenerated.goal_world, original.goal_world)
                self.assertEqual(regenerated.goal_mode, original.goal_mode)
                self.assertEqual(regenerated.barker_access, original.barker_access)
                self.assertEqual(regenerated.counter_mode, original.counter_mode)
                self.assertEqual(regenerated.required_coins, original.required_coins)
                self.assertEqual(regenerated.total_barker_coins, original.total_barker_coins)
                self.assertEqual(regenerated.active_locations, original.active_locations)
                self.assertEqual(regenerated.early_world_accesses, original.early_world_accesses)
                if original.goal_world is not None:
                    for count in ({0, max(0, original.required_coins - 1), original.required_coins}
                                  if original.barker_access else {0}):
                        original_state = CollectionState(original.multiworld)
                        regenerated_state = CollectionState(regenerated.multiworld)
                        if original.barker_access:
                            for _ in range(count):
                                original_state.collect(original.create_item(BARKER_COIN), prevent_sweep=True)
                                regenerated_state.collect(regenerated.create_item(BARKER_COIN), prevent_sweep=True)
                        else:
                            original_state.collect(original.create_item(UNLOCKS[original.goal_world]),
                                                   prevent_sweep=True)
                            regenerated_state.collect(regenerated.create_item(UNLOCKS[regenerated.goal_world]),
                                                      prevent_sweep=True)
                        self.assertEqual(original_state.can_reach_region(WORLDS[original.goal_world], 1),
                                         regenerated_state.can_reach_region(WORLDS[regenerated.goal_world], 1))

    def test_high_barker_minimal_fill_has_world_access_chain(self):
        options = dict(starting_world=2, goal=1, goal_world=1, goal_world_access=1,
                       barker_coins_required=40, minigame_checks=0, hole_in_one_checks=0,
                       barker_coin_checks=0, world_secrets=0, shop_checks=0, barker_shop_checks=1)
        for seed in range(100):
            with self.subTest(seed=seed):
                multiworld = generate(options, seed=seed, fill=True)
                world = multiworld.worlds[1]
                self.assertEqual(len(world.early_world_accesses), 7)
                chain_world = world.starting_world
                for index in world.early_world_accesses:
                    location = multiworld.get_location(f"{HOLES[chain_world * 3]} - Complete", 1)
                    self.assertTrue(location.locked)
                    self.assertEqual(location.item.name, UNLOCKS[index])
                    self.assertNotIn(index, (world.starting_world, world.goal_world))
                    chain_world = index
                self.assertFalse(multiworld.get_unfilled_locations())
                self.assertTrue(multiworld.can_beat_game())
