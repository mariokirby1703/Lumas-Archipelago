"""Generation regressions: Auburn is the only free-roam starting district."""
import unittest
from BaseClasses import CollectionState
from worlds.lego_city_undercover.tests.test_generation import GenerationTests
from worlds.lego_city_undercover.bridge.area_passes import AUBURN_OPENING_KEYS


class AreaRegionStartTests(unittest.TestCase):
    def test_cherry_station_requires_cherry_pass(self):
        multi, world = GenerationTests().build(dict(
            area_pass_items=True, experimental_area_restrictions=True,
            early_criminal_scan=True, early_detective_scan=True))
        state = CollectionState(multi)
        self.assertTrue(multi.get_region('District: SF_Docks', 1).can_reach(state))
        self.assertFalse(multi.get_region('District: SF_Residential', 1).can_reach(state))
        self.assertFalse(multi.get_region('Police Station', 1).can_reach(state))
        # The native entrance in Cherry Tree Hills is NOT a free starting-area
        # shortcut merely because police station checks were observed early.
        cherry_item = next(loc.item for loc in multi.get_locations(1)
                           if loc.item and loc.item.name == 'Area Pass: SF_Residential')
        state.collect(cherry_item, True)
        self.assertTrue(multi.get_region('District: SF_Residential', 1).can_reach(state))
        self.assertTrue(multi.get_region('Police Station', 1).can_reach(state))
        self.assertTrue(world.fill_slot_data()['logic_coverage']['police_station_requires_cherry_pass'])

    def test_early_local_items_are_only_on_auburn_opening_checks(self):
        multi, world = GenerationTests().build(dict(
            area_pass_items=True, experimental_area_restrictions=True,
            early_criminal_scan=True, early_detective_scan=True))
        by_name = {row['name']: key for key, row in world.active_catalogue.items()}
        tracked = {'Area Pass: SF_Residential', 'Ability: Police', 'Progressive Police',
                   'Ability: Criminal Scan', 'Ability: Detective Scan'}
        for location in multi.get_locations(1):
            if location.item and location.item.name in tracked:
                key = by_name.get(location.name)
                self.assertIn(key, AUBURN_OPENING_KEYS)
                self.assertEqual(location.parent_region.name, 'Opening before Police')

    def test_area_seed_rejects_native_open_world_bootstrap(self):
        with self.assertRaisesRegex(ValueError, 'linear story mode'):
            GenerationTests().build(dict(area_pass_items=True,
                experimental_area_restrictions=True, story_mode='open_world'))


if __name__ == '__main__':
    unittest.main()
