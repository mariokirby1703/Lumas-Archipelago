import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from level_progress import parse_level_progress,completed_level_keys
from client_checks import changed_checks


class LevelProgressTests(unittest.TestCase):
    def fixture(self,path='Standalones\\Mine',flags=0x36):
        descriptor=bytearray(0x80);descriptor[:len(path)]=path.encode('ascii')
        record=bytearray(20);record[10]=flags;record[4]=record[5]=1
        return descriptor,record

    def test_saved_completion_is_independent_of_current_scene_and_hero(self):
        descriptor,record=self.fixture()
        row=parse_level_progress(descriptor,record,4)
        state=dict(status='read',records=[row])
        keys=completed_level_keys(state)
        self.assertIn('mission:mine:Complete',keys)
        self.assertIn('mission:mine:LEGO City Hero',keys)
        self.assertIn('mission:mine:TR',keys)
        self.assertNotIn('mission:mine:Police Shield',keys)
        record[10]=0;row=parse_level_progress(descriptor,record,4)
        keys=completed_level_keys(dict(status='read',records=[row]))
        self.assertNotIn('mission:mine:Complete',keys)
        self.assertIn('mission:mine:LEGO City Hero',keys)

    def test_reconcile_existing_seed_after_return_to_city(self):
        row=parse_level_progress(*self.fixture(),4)
        snapshot=dict(objectives=dict(records=[]),pickup_bits=[],level_progress=dict(status='read',records=[row]))
        catalogue={'1':dict(key='mission:mine:Complete'),'2':dict(key='mission:prison:Complete')}
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[1])
        self.assertEqual(changed_checks(catalogue,None,snapshot,{1})[0],[])
        snapshot['level_progress']['status']='unresolved'
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[])

    def test_city_and_secondary_areas_do_not_become_standalone_completions(self):
        for path in ('Lego_City','Standalones\\Prison\\Prison_Hospital'):
            self.assertIsNone(parse_level_progress(*self.fixture(path),0))
        descriptor,record=self.fixture();record[4]=2
        with self.assertRaises(ValueError):parse_level_progress(descriptor,record,4)

    def test_shared_resource_requires_all_native_mission_completions(self):
        a=parse_level_progress(*self.fixture('Standalones\\Blackwells_Mansion'),11)
        b=dict(a,complete=False,level_index=15)
        self.assertEqual(completed_level_keys(dict(status='read',records=[a,b])),set())
        b['complete']=True
        self.assertEqual(completed_level_keys(dict(status='read',records=[a,b])),
                         {'mission:blackwells_mansion:Complete'})
