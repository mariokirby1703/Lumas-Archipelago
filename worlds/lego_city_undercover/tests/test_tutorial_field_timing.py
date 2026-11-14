import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from tutorial_field_timing import TutorialFieldTiming

class TutorialTimingTests(unittest.TestCase):
    def setUp(self):
        self.now=100.;self.gate=TutorialFieldTiming(lambda:self.now)
        self.scene={'status':'read','level':'0x1234'}
    def test_waits_for_stable_scene_and_does_not_restart_each_poll(self):
        self.assertFalse(self.gate.ready(1,self.scene))
        self.now+=7.9;self.assertFalse(self.gate.ready(1,self.scene))
        self.now+=0.1;self.assertTrue(self.gate.ready(1,self.scene))
        self.now+=10;self.assertTrue(self.gate.ready(1,self.scene))
    def test_scene_reload_and_process_change_restart_delay(self):
        self.gate.ready(1,self.scene);self.now+=9
        self.assertFalse(self.gate.ready(1,dict(self.scene,level='0x5678')))
        self.now+=9;self.assertFalse(self.gate.ready(2,self.scene))
    def test_unresolved_scene_resets_delay(self):
        self.gate.ready(1,self.scene);self.now+=9
        self.assertFalse(self.gate.ready(1,{'status':'unresolved'}))
        self.assertFalse(self.gate.ready(1,self.scene))
        self.now+=8;self.assertTrue(self.gate.ready(1,self.scene))
