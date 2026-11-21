import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from superbuild_reader import bind_superbuild
from client_checks import changed_checks

class MissionBuildBindingTests(unittest.TestCase):
    def setUp(self):
        self.world=Path(__file__).resolve().parents[1]
        self.bindings=json.loads((self.world/'bridge/mission_superbuild_bindings.json').read_text())
    def test_seven_original_ids_and_mission_sections_are_retained(self):
        catalogue=json.loads((self.world/'catalogue.json').read_text())['locations']
        self.assertEqual(len(self.bindings),7)
        for row in self.bindings:
            native=catalogue['objective:'+row['objective']]
            self.assertEqual(native['id'],row['ap_id']);self.assertEqual(native['category'],'super_builds')
            self.assertIn('/standalones/'+row['mission']+'/',native['source'])
            self.assertEqual(native['building_brick_cost']['amount'],row['build_cost'])
    def test_original_template_name_is_bound_only_in_exact_mission_and_owner_scene(self):
        for row in self.bindings:
            live=dict(name='#cg_123_'+row['native_suffix'],scene_name=row['scene'],position=[1,2,3],native_build_value=row['build_cost'])
            self.assertEqual(bind_superbuild(live,self.bindings,row['mission']),row['objective'])
            self.assertIsNone(bind_superbuild(live,self.bindings,'other_mission'))
            self.assertIsNone(bind_superbuild(dict(live,scene_name='builder_template'),self.bindings,row['mission']))
            self.assertIsNone(bind_superbuild(dict(live,scene_conflict=True),self.bindings,row['mission']))
            self.assertIsNone(bind_superbuild(dict(live,native_build_value=0),self.bindings,row['mission']))
            self.assertIsNone(bind_superbuild(dict(live,name=live['name']+'_decoration'),self.bindings,row['mission']))
    def test_native_completion_still_requires_observed_final_state(self):
        for row in self.bindings:
            c={str(row['ap_id']):dict(key='objective:'+row['objective'],status='native_objective',runtime=dict(kind='objective',name=row['objective']))}
            for completed in (False,True):
                snap=dict(objectives=dict(records=[]),pickup_bits=[],superbuilds=dict(status='read',records=[dict(complete=completed,objective_name=row['objective'])]))
                self.assertEqual(changed_checks(c,None,snap)[0],[row['ap_id']] if completed else [])

    def test_template_footer_parser_rejects_unknown_versions_and_bad_costs(self):
        import struct
        sys.path.insert(0,str(self.world/'tools'))
        from research_mission_superbuilds import parse_template
        prefix=bytearray(40);struct.pack_into('<II',prefix,0,8,1);struct.pack_into('<f',prefix,24,22000.)
        name=b'CableCar_SB\0';payload=bytes(prefix)+bytes([len(name)])+name+bytes(22)
        self.assertEqual(parse_template(payload),('CableCar_SB',22000))
        with self.assertRaises(ValueError):parse_template(payload[:-1])
        broken=bytearray(payload);struct.pack_into('<I',broken,0,6)
        with self.assertRaises(ValueError):parse_template(bytes(broken))
        struct.pack_into('<I',broken,0,8);struct.pack_into('<f',broken,24,float('nan'))
        with self.assertRaises(ValueError):parse_template(bytes(broken))
