import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from station_exit import StationExitGate
from native_context_policy import allows_native_command

class StationExitGateTests(unittest.TestCase):
    def probe(self,distance,owner=100):return dict(owner=owner,distance_squared=distance**2)
    def test_entry_spawn_does_not_eject_player(self):
        gate=StationExitGate()
        for _ in range(5):self.assertFalse(gate.update(1,self.probe(0.6),46))
    def test_walk_away_then_return_arms_existing_exit(self):
        gate=StationExitGate()
        self.assertFalse(gate.update(1,self.probe(5),46))
        self.assertFalse(gate.update(1,self.probe(1.2),46))
        self.assertTrue(gate.update(1,self.probe(0.6),46))
        gate.mark_triggered()
        self.assertFalse(gate.update(1,self.probe(0.6),46))
    def test_other_scene_resets_arming_and_dispatch_latch(self):
        gate=StationExitGate();gate.update(1,self.probe(5),46);gate.mark_triggered()
        self.assertFalse(gate.update(1,None,46))
        self.assertFalse(gate.update(1,self.probe(0.6),46))
        self.assertFalse(gate.triggered)
    def test_interactions_and_vehicles_never_dispatch_exit(self):
        gate=StationExitGate();gate.update(1,self.probe(5),46)
        for context in (25,27,63,157,250):
            self.assertFalse(gate.update(1,self.probe(0.6),context))
            self.assertFalse(allows_native_command(context,12))
        self.assertTrue(gate.update(1,self.probe(0.6),46))
    def test_different_process_or_level_owner_must_rearm(self):
        gate=StationExitGate();gate.update(1,self.probe(5),46)
        self.assertFalse(gate.update(2,self.probe(0.6),46))
        gate.update(2,self.probe(5),46)
        self.assertFalse(gate.update(2,self.probe(0.6,owner=200),46))

    def test_only_verified_first_lobby_resume_phase_is_eligible(self):
        from station_exit import can_resume_first_lobby
        lobby={'LCPD_MainframeActive':False,'LCPD_LobbyEntered':2}
        story={'jobs':{'PDA':{'acquired':False},'Flow_Setup':{'Flow_Act':1},
                       'Flow_Setup.Act_1':{'Act1_Mission':1,'Act1_Stage':2},
                       'Flow_Setup.Act_1.LCPD.LCPD_Level.LCPD_Lobby':lobby}}
        self.assertTrue(can_resume_first_lobby(story))
        lobby['LCPD_MainframeActive']=True
        self.assertFalse(can_resume_first_lobby(story))
        lobby['LCPD_LobbyEntered']=1
        self.assertTrue(can_resume_first_lobby(story))
        story['jobs']['PDA']['acquired']=True
        self.assertFalse(can_resume_first_lobby(story))
        del story['jobs']['PDA']
        self.assertFalse(can_resume_first_lobby(story))
        self.assertFalse(can_resume_first_lobby({}))
