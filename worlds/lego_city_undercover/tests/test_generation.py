import unittest
from argparse import Namespace
from BaseClasses import MultiWorld, CollectionState
from worlds.lego_city_undercover import LCUWorld, TOKEN, CATALOGUE
from Fill import distribute_items_restrictive


class GenerationTests(unittest.TestCase):
    def test_requested_packages_and_skin_classification(self):
        from BaseClasses import ItemClassification
        multi,world=self.build()
        names=[item.name for item in multi.itempool]
        self.assertEqual(names.count('Super Bricks 10,000'),5)
        self.assertEqual(names.count('Super Bricks 1,000'),20)
        self.assertEqual(world.create_item('Super Bricks 10,000').classification,ItemClassification.useful)
        self.assertEqual(world.create_item('Character: MINER').classification,ItemClassification.progression)
        for name in ('Studs 1,000','Studs 10,000','Studs 100,000','Super Bricks 100','Super Bricks 250'):
            self.assertEqual(world.create_item(name).classification,ItemClassification.filler)
        self.assertEqual(len(names),len(multi.get_unfilled_locations()))

    def build(self,changes=None):
        multi=MultiWorld(1);multi.game[1]=LCUWorld.game;multi.player_name={1:'LCUTest'};multi.set_seed(1234)
        args=Namespace()
        for name,option in LCUWorld.options_dataclass.type_hints.items():
            setattr(args,name,{1:option.from_any((changes or {}).get(name,option.default))})
        multi.set_options(args);multi.state=CollectionState(multi);world=multi.worlds[1]
        world.generate_early();world.create_regions();world.create_items();world.pre_fill()
        return multi,world

    def test_default_fill_and_goal(self):
        multi,world=self.build()
        self.assertEqual(len(multi.itempool),len(multi.get_unfilled_locations()))
        distribute_items_restrictive(multi)
        self.assertTrue(multi.can_beat_game())
        self.assertTrue(world.fill_slot_data()['native_grants'])
        self.assertFalse(world.fill_slot_data()['native_locks'])
        self.assertEqual(world.fill_slot_data()['native_reward_suppression'],'poll_after_checks')
        self.assertNotIn('unverified_clues',{r['category'] for r in world.active_catalogue.values()})

    def test_whole_and_quarters_are_exclusive(self):
        for value,included,excluded in ((1,'whole_shields','shield_quarters'),(2,'shield_quarters','whole_shields')):
            _,world=self.build({'police_shields':value})
            categories={r['category'] for r in world.active_catalogue.values()}
            self.assertIn(included,categories);self.assertNotIn(excluded,categories)

    def test_unverified_opt_in_and_ids(self):
        _,world=self.build({'include_unverified':True})
        self.assertEqual(len(world.active_catalogue),len(CATALOGUE['locations'])-len(CATALOGUE['levels']))
        self.assertEqual(len(LCUWorld.item_name_to_id),len(set(LCUWorld.item_name_to_id.values())))
    def test_linear_police_is_guaranteed_on_an_opening_check(self):
        from worlds.lego_city_undercover.bridge.opening_logic import NO_POLICE_KEYS,POLICE_ITEMS
        multi,world=self.build()
        state=CollectionState(multi)
        for key,row in world.active_catalogue.items():
            self.assertEqual(multi.get_location(row['name'],1).can_reach(state),key in NO_POLICE_KEYS)
        location=multi.get_location(world.early_police_location,1)
        self.assertTrue(location.locked)
        self.assertIn(location.item.name,POLICE_ITEMS)
        self.assertTrue(location.can_reach(state))
        state.collect(location.item,True)
        self.assertTrue(all(loc.can_reach(state) for loc in multi.get_locations(1)))
    def test_open_world_keeps_unrestricted_checks_without_local_police_placement(self):
        multi,world=self.build({'story_mode':'open_world'})
        self.assertIsNone(world.early_police_location)
        self.assertTrue(all(loc.can_reach(CollectionState(multi)) for loc in multi.get_locations(1)))
    def test_character_only_pool_can_supply_opening_police(self):
        multi,world=self.build({'ability_items':False})
        self.assertEqual(multi.get_location(world.early_police_location,1).item.name,'Character: COP')
    def test_linear_generation_rejects_missing_police_instead_of_an_unbeatable_seed(self):
        with self.assertRaisesRegex(ValueError,'requires Police'):
            self.build({'ability_items':False,'character_items':False})
    def test_opening_police_respects_excluded_locations(self):
        from worlds.lego_city_undercover.bridge.opening_logic import NO_POLICE_KEYS
        names={r['name'] for k,r in CATALOGUE['locations'].items() if k in NO_POLICE_KEYS}
        target=CATALOGUE['locations']['story_arrest:clown_1']['name']
        multi,world=self.build({'exclude_locations':names-{target}})
        self.assertEqual(world.early_police_location,target)
        with self.assertRaisesRegex(ValueError,'no enabled opening location'):
            self.build({'exclude_locations':names})
    def test_linear_police_does_not_silently_override_non_local_items(self):
        with self.assertRaisesRegex(ValueError,'local opening Police'):
            self.build({'non_local_items':{'Ability: Police','Character: COP'}})
