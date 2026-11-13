from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from object_activity import ObjectActivityTracker


class ObjectActivityTests(unittest.TestCase):
    def state(self,flags='0x200',level='level1',name='safe'):
        return dict(status='read',level=level,player_position=[0,0,0],fields=[dict(address='a',name=name,
                    family='Tresor',position=[1,0,0],state_flags=flags)])

    def test_flag_transition_is_evidence_not_completion(self):
        tracker=ObjectActivityTracker()
        self.assertEqual(tracker.update(self.state()),[])
        events=tracker.update(self.state('0x206'))
        self.assertEqual(events[0]['changes']['state_flags'],dict(before='0x200',after='0x206'))
        self.assertFalse(events[0]['automatic_check'])
        self.assertEqual(tracker.update(self.state('0x206')),[])

    def test_loading_and_address_reuse_do_not_create_false_actions(self):
        tracker=ObjectActivityTracker();tracker.update(self.state())
        self.assertEqual(tracker.update(self.state('0x206',level='level2')),[])
        self.assertEqual(tracker.update(self.state('0',level='level2',name='different')),[])
        tracker.update(dict(status='unresolved'))
        self.assertEqual(tracker.update(self.state('0x206')),[])
