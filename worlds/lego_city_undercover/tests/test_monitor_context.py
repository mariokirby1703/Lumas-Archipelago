from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from monitor_context import ContextTracker


class ContextHistoryTests(unittest.TestCase):
    def test_changes_reentries_and_unknown_samples(self):
        tracker = ContextTracker()
        default = dict(status='read', index=46, name='Default')
        first = tracker.update(default)
        self.assertTrue(first['initial'])
        self.assertIsNone(tracker.update(default))
        self.assertIsNone(tracker.update(dict(status='no_action')))
        changed = tracker.update(dict(status='read', index=40, name='Brick Grab'))
        self.assertEqual(changed['previous']['name'], 'Default')
        self.assertFalse(changed['initial'])
        self.assertEqual(tracker.update(default)['previous']['index'], 40)
