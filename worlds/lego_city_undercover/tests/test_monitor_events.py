import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from monitor_events import EventTracker


class MonitorEventsTests(unittest.TestCase):
    def test_pending_unlock_without_found_then_save_commit(self):
        tracker = EventTracker(dict(objectives={}, superbricks={}))
        old = self.snapshot()
        tracker.update(old)
        pending = copy.deepcopy(old)
        pending['characters'][0]['pending_grant'] = True
        event, = tracker.update(pending)
        self.assertEqual(event['kind'], 'unlock')
        committed = copy.deepcopy(pending)
        committed['characters'][0].update(pending_grant=False, found_bit=True, owned_byte=1)
        self.assertEqual(tracker.update(committed), [])

    def snapshot(self):
        return dict(objectives=dict(records=[dict(name_hash=4, bit_index=7, candidate_complete=False)]),
                    pickup_bits=[], characters=[dict(model_id=1, group='character', internal_name='Test',
                                                     found_bit=False, owned_byte=0, pending_grant=False)],
                    abilities={'GrappleGun': False})

    def test_baseline_then_correlated_activity_reward_once(self):
        tracker = EventTracker(dict(objectives={}, superbricks={}))
        old = self.snapshot()
        self.assertEqual(tracker.update(old), [])
        new = copy.deepcopy(old)
        new['objectives']['records'][0]['candidate_complete'] = True
        new['characters'][0]['found_bit'] = True
        self.assertEqual([e['kind'] for e in tracker.update(new)], ['city_flag', 'discovery'])
        self.assertEqual(tracker.update(new), [])
        self.assertEqual(tracker.update(old), [])
        self.assertEqual(tracker.update(new), [])

    def test_pending_commit_is_not_new_ownership_or_discovery(self):
        tracker = EventTracker(dict(objectives={}, superbricks={}))
        old = self.snapshot()
        old['characters'][0].update(found_bit=True, pending_grant=True)
        tracker.update(old)
        new = copy.deepcopy(old)
        new['characters'][0].update(owned_byte=1, pending_grant=False)
        self.assertEqual(tracker.update(new), [])

    def test_unknown_pickup_and_ability(self):
        tracker = EventTracker(dict(objectives={}, superbricks={}))
        old = self.snapshot()
        tracker.update(old)
        new = copy.deepcopy(old)
        new['pickup_bits'] = [2491]
        new['abilities']['GrappleGun'] = True
        events = tracker.update(new)
        self.assertEqual([e['kind'] for e in events], ['superbrick', 'ability'])
        self.assertIn('noch nicht zugeordnet', events[0]['text'])
