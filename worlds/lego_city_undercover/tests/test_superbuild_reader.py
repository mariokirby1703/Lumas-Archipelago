import struct
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from superbuild_reader import parse_superbuild
from client_checks import changed_checks
from research_profile import symbol_hash


class SuperBuildTests(unittest.TestCase):
    def test_native_build_value_keeps_large_quotes_distinct_from_affordability_logic(self):
        data=bytearray(0x1e8);struct.pack_into('<Q',data,0,0xc300f8)
        for cost in (8000,20000,30000,40000,50000,100000):
            struct.pack_into('<f',data,0x1d4,cost)
            row=parse_superbuild(data,0);self.assertEqual(row['native_build_value'],cost)
            self.assertFalse(row['cost_logic_verified'])
        struct.pack_into('<f',data,0x1d4,float('nan'))
        self.assertIsNone(parse_superbuild(data,0)['native_build_value'])

    def test_only_completed_state_and_flag_count(self):
        data=bytearray(0x1e8);struct.pack_into('<Q',data,0,0xc300f8)
        data[0x58:0x58+4]=b'Giz\0'
        for state,flags,complete in ((0,0,False),(3,4,False),(4,4,False),(5,0,False),(5,4,True)):
            struct.pack_into('<HI',data,0x1e2,state,flags)
            self.assertEqual(parse_superbuild(data,0)['complete'],complete)
        with self.assertRaises(ValueError):parse_superbuild(data[:-1],0)

    def test_direct_build_state_overrides_unset_scanner_flag(self):
        catalogue={'1':dict(key='objective:Mine_CableCar',status='native_objective',
                           runtime=dict(kind='objective',name='Mine_CableCar'))}
        row=dict(complete=True,objective_name='Mine_CableCar')
        snapshot=dict(objectives=dict(records=[dict(name_hash=symbol_hash('Mine_CableCar'),candidate_complete=False)]),
                      pickup_bits=[],superbuilds=dict(status='read',records=[row]))
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[1])
        self.assertEqual(changed_checks(catalogue,None,snapshot,{1})[0],[])
        row['objective_name']=None
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[])
