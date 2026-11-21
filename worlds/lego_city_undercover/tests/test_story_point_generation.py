import unittest
import worlds.lego_city_undercover.tests.test_generation as generation
from worlds.lego_city_undercover.bridge.story_points import COMPLETIONS
class StoryPointGenerationTests(unittest.TestCase):
    def test_option_controls_new_locations_and_unreviewed_logic_cannot_hide_progression(self):
        _,world=generation.GenerationTests().build()
        for row in COMPLETIONS:
            self.assertIn(row['ap_key'],world.active_catalogue)
            location=world.multiworld.get_location(world.active_catalogue[row['ap_key']]['name'],world.player)
            self.assertEqual(location.parent_region.name,'Story Chapter '+str(row['chapter']))
            self.assertFalse(location.item_rule(world.create_item('Progressive Police')))
            self.assertTrue(location.item_rule(world.create_item('Studs 1,000')))
        _,disabled=generation.GenerationTests().build({'story_milestones':False})
        self.assertFalse(any(r['ap_key'] in disabled.active_catalogue for r in COMPLETIONS))
    def test_mission_builds_reside_in_the_actual_assignment_sections(self):
        _,world=generation.GenerationTests().build()
        for key,row in world.active_catalogue.items():
            if row.get('mission_superbuild'):
                location=world.multiworld.get_location(row['name'],world.player)
                self.assertIn(row['section'],location.parent_region.name.casefold())

    def test_normal_seed_cannot_advertise_symbolic_open_world_as_native(self):
        with self.assertRaisesRegex(ValueError,'native Open World'):
            generation.GenerationTests().build({'story_mode':'open_world'})
