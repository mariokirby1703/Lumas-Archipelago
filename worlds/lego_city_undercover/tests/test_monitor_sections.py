import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from monitor_sections import SectionTracker, location_heading, story_heading


class SectionTests(unittest.TestCase):
    def test_area_and_story_remain_distinct(self):
        self.assertIn('Gebiet: Albatross Island', location_heading({'native_tile':'IS_Prison_Island_1525'}))
        self.assertIn('nicht erkannt', location_heading({}))
        self.assertIn('unabhängig vom Gebiet', story_heading(self.snap()['story']))
    def snap(self, tile='SF_Residential_0918', mission=5):
        return dict(location=dict(native_tile=tile), story=dict(jobs={
            'Flow_Setup': {'Flow_Act': 1}, 'Flow_Setup.Act_1': {'Act1_Mission': mission, 'Act1_Stage': 1}}))

    def test_initial_then_tile_change_stays_same_area(self):
        t = SectionTracker()
        self.assertEqual(len(t.update(self.snap())), 2)
        self.assertEqual(t.update(self.snap('SF_Residential_1020')), [])
        event, = t.update(self.snap('SF_Docks_0918'))
        self.assertEqual(event['text'], '----- Auburn -----')

    def test_reenter_area_and_ignore_missing_or_transition(self):
        t = SectionTracker()
        t.update(self.snap())
        self.assertEqual(t.update({}), [])
        self.assertEqual(t.update(self.snap(mission=0)), [])
        self.assertEqual(t.update(self.snap(mission=5)), [])
        event, = t.update(self.snap(mission=6))
        self.assertEqual(event['kind'], 'story_section')
        t.update(self.snap('SF_Docks_0918', mission=6))
        event, = t.update(self.snap(mission=6))
        self.assertIn('Cherry Tree Hills', event['text'])
