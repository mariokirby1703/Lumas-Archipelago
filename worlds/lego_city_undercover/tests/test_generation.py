import unittest
from argparse import Namespace
from BaseClasses import MultiWorld, CollectionState
from worlds.lego_city_undercover import LCUWorld, TOKEN, CATALOGUE
from Fill import distribute_items_restrictive


class GenerationTests(unittest.TestCase):
    def build(self,changes=None):
        multi=MultiWorld(1);multi.game[1]=LCUWorld.game;multi.player_name={1:'LCUTest'};multi.set_seed(1234)
        args=Namespace()
        for name,option in LCUWorld.options_dataclass.type_hints.items():
            setattr(args,name,{1:option.from_any((changes or {}).get(name,option.default))})
        multi.set_options(args);multi.state=CollectionState(multi);world=multi.worlds[1]
        world.generate_early();world.create_regions();world.create_items()
        return multi,world

    def test_default_fill_and_goal(self):
        multi,world=self.build()
        self.assertEqual(len(multi.itempool),len(multi.get_unfilled_locations()))
        distribute_items_restrictive(multi)
        self.assertTrue(multi.can_beat_game())
        self.assertFalse(world.fill_slot_data()['native_grants'])
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
