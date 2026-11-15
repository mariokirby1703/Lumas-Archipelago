from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from pickup_reader import read_loaded_pickups


class PickupWriterGuardTests(unittest.TestCase):
    def fixture(self,enabled):
        q=lambda n:struct.pack('<Q',n)
        node=bytearray(0x198)
        struct.pack_into('<Q',node,0,0xc2ed28)
        struct.pack_into('<Q',node,0x48,0x10000)
        node[0x58:0x5d]=b'P_pup';node[0x193]=12
        struct.pack_into('<3f',node,0x78,1,2,3)
        struct.pack_into('<H',node,0x160,2)
        bank=bytearray(1600);bank[12]=1
        values={0x10000:q(0xd89948),0x17ec808:q(0x20000),0x20120:bytes(bank),
                0x1c7a830:q(0x30000),0x3335d:bytes([enabled]),0x1165910:struct.pack('<I',38),
                0x1c9df10:q(0x40000),0x40000:q(0x50000),0x50618:struct.pack('<I',0x4000000),
                0x100e0:q(0x60000),0x10020:q(0x70000),0x70b18:q(0x80000),
                0x80068:q(0x90000),0x90000:b'SF_Docks_1200\0'.ljust(32,b'\0'),0x60000:bytes(node),
                0x80208:bytes([12,0]),0x60028:q(0),0x60160:struct.pack('<H',2)}
        def read(address,size):
            value=values[address];self.assertEqual(len(value),size);return value
        return values,read

    def snapshot(self,read):
        with patch('pickup_reader.scene_component',return_value=0x10000):
            return read_loaded_pickups(read,0,dict(level=1,table=2))

    def test_city_writer_guard_required_even_with_matching_type_and_index(self):
        values,read=self.fixture(1)
        active=self.snapshot(read)['objects'][0]
        self.assertEqual(active['collection_bit'],96);self.assertTrue(active['writer_enabled'])
        self.assertEqual(active['grid_width'],38)
        values[0x3335d]=b'\0'
        inactive=self.snapshot(read)['objects'][0]
        self.assertIsNone(inactive['collection_bit'])
        self.assertTrue(inactive['native_collected'],'transient collection event remains distinct from city persistence')
        self.assertFalse(inactive['writer_enabled'])

    def test_mode_transition_during_read_is_rejected(self):
        values,read=self.fixture(1);calls=0
        def changing(address,size):
            nonlocal calls
            if address==0x3335d:
                calls+=1
                if calls>1:return b'\0'
            return read(address,size)
        with self.assertRaisesRegex(RuntimeError,'Pickup state changed'):self.snapshot(changing)

    def test_temporary_collection_flag_reset_is_not_a_stable_collection(self):
        values,read=self.fixture(1)
        values[0x60160]=bytes(2)
        with self.assertRaisesRegex(RuntimeError,'Pickup state changed'):self.snapshot(read)
