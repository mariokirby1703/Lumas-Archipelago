import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from goals import native_goal_complete,ASSIGNMENTS
from level_progress import parse_level_progress,completed_level_keys
from source_logic import source_requirement


class GoalsAndSourceLogicTests(unittest.TestCase):
    def test_native_goal_requires_loaded_consistent_completion(self):
        self.assertFalse(native_goal_complete({},0))
        final=dict(mission='moon_base',complete=True)
        snapshot=dict(level_progress=dict(status='read',records=[final]))
        self.assertTrue(native_goal_complete(snapshot,0));self.assertFalse(native_goal_complete(snapshot,1))
        snapshot['level_progress']['records']=[dict(mission=a,complete=True) for a in ASSIGNMENTS]
        self.assertTrue(native_goal_complete(snapshot,1));self.assertFalse(native_goal_complete(snapshot,2))
        snapshot['level_progress']['status']='not_initialized'
        self.assertFalse(native_goal_complete(snapshot,0))

    def test_blackwell_progress_has_independent_collectibles_and_legacy_aggregate(self):
        rows=[]
        for number in (1,2):
            d=bytearray(128);path=b'Standalones\\Blackwells_Mansion';d[:len(path)]=path
            name=f'blackwells_mansion_{number}'.encode();d[64:64+len(name)]=name
            record=bytearray(20);record[10]=0x11 if number==1 else 2
            rows.append(parse_level_progress(d,record,number))
        keys=completed_level_keys(dict(status='read',records=rows))
        self.assertIn('mission:blackwells_mansion_1:Complete',keys)
        self.assertIn('mission:blackwells_mansion_1:TL',keys)
        self.assertIn('mission:blackwells_mansion_2:TR',keys)
        self.assertNotIn('mission:blackwells_mansion_2:Complete',keys)
        self.assertNotIn('mission:blackwells_mansion:Complete',keys)

    def test_requirements_use_source_not_reward(self):
        for kind,name,expected in [('CLass','Fireman','Firefighter'),('Ability','EnergyGun','Color Gun'),
                                   ('Class','Worker','Construction Worker'),('Ability','SuperStrength','Rex Fury')]:
            self.assertEqual(source_requirement(dict(source_requirements=dict(lockType=kind,lockName=name))),expected)
        self.assertIsNone(source_requirement(dict(category='character_tokens')))
