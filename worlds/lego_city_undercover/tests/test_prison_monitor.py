import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from monitor_events import EventTracker
from monitor_sections import SectionTracker


class PrisonMonitorTests(unittest.TestCase):
    def snapshot(self, finished):
        return dict(objectives={'records':[]},pickup_bits=[],characters=[],abilities={},
                    story={'jobs':{'Standalones.Prison':{'Finished':finished}}})

    def test_transient_mission_values_log_both_directions(self):
        t = EventTracker({'objectives':{},'superbricks':{}})
        self.assertEqual(t.update(self.snapshot(0)), [])
        event, = t.update(self.snapshot(1))
        self.assertEqual(event['kind'], 'mission_state')
        self.assertFalse(event['persistent_completion_verified'])
        event, = t.update(self.snapshot(0))
        self.assertEqual((event['before'],event['after']), (1,0))

    def test_island_name(self):
        event, = SectionTracker().update({'location':{'native_tile':'IS_Prison_Island_1525'}})
        self.assertEqual(event['text'], '----- Albatross Island -----')
