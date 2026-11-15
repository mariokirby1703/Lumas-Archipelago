import struct
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from superbuild_reader import parse_superbuild, bind_superbuild, read_superbuilds
from unittest.mock import patch
import json
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


class CitySuperBuildTests(unittest.TestCase):
    def test_city_binding_requires_exact_name_and_position(self):
        bindings=json.loads((Path(__file__).resolve().parents[1]/'bridge/superbuild_bindings.json').read_text())
        binding=next(b for b in bindings if b.get('objective')=='SF_DO_0815_VehDrop')
        row=dict(name=binding['native_name'],position=binding['position'])
        self.assertEqual(bind_superbuild(row,bindings,None),'SF_DO_0815_VehDrop')
        self.assertIsNone(bind_superbuild(dict(row,position=[0,0,0]),bindings,None))
        self.assertIsNone(bind_superbuild(dict(row,name='VEHICLE_DROP_GSB'),bindings,None))
        self.assertIsNone(bind_superbuild(row,bindings+[dict(binding,objective='other')],None))

    def test_city_scene_is_read_when_player_scene_has_no_component(self):
        import superbuild_reader as reader
        base=0x10000000;registry=0x20000;entry=0x30000;owner=0x40000
        level=0x50000;table=0x60000;component=0x70000;node=0x80000
        pointers={base+0x1C402D8:registry,entry+0xD8:owner,owner+0xB18:1,
                  owner+0xBB0:level,level+0xA0:0x51000,0x51000+0xC0:table,
                  component:base+0xC30608,component+0xE0:node}
        binding=json.loads((Path(reader.__file__).parent/'superbuild_bindings.json').read_text())[1]
        data=bytearray(0x1E8);struct.pack_into('<Q',data,0,base+0xC300F8)
        struct.pack_into('<Q',data,0x48,component)
        name=binding['native_name'].encode();data[0x58:0x58+len(name)]=name
        struct.pack_into('<3f',data,0x78,*binding['position'])
        struct.pack_into('<HI',data,0x1E2,5,4)
        raw=struct.pack('<Q',entry)+bytes(16376)
        def read(address,size):
            if registry+0x18<=address<registry+0x18+16384:
                offset=address-registry-0x18;return raw[offset:offset+size]
            if address==node:return bytes(data)
            if address==node+0x1E2:return bytes(data[0x1E2:0x1E8])
            raise AssertionError((address,size))
        scene=dict(level=0x90000,table=0x91000)
        with patch.object(reader,'pointer',side_effect=lambda r,a:pointers.get(a,0)), \
             patch.object(reader,'player_scene',return_value=scene), \
             patch.object(reader,'scene_component',side_effect=lambda r,b,s,m:component if s['table']==table else 0):
            result=read_superbuilds(read,base,None)
        self.assertEqual(len(result['records']),1)
        row=result['records'][0];self.assertTrue(row['complete'])
        self.assertEqual(row['objective_name'],'SF_DO_0815_VehDrop')
        catalogue={'1167252269':dict(key='objective:SF_DO_0815_VehDrop',status='native_objective',runtime=dict(kind='objective',name='SF_DO_0815_VehDrop'))}
        snapshot=dict(objectives=dict(records=[]),pickup_bits=[],superbuilds=result)
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[1167252269])
        self.assertEqual(changed_checks(catalogue,None,snapshot,{1167252269})[0],[])
