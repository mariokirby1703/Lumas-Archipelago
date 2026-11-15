import sys
from pathlib import Path
import struct
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from vehicle_reader import read_ride


class VehicleReaderTests(unittest.TestCase):
    def fixture(self,getter=0x506fe0):
        data={0x1c7d3e0:struct.pack('<Q',0x10000),0x10428:struct.pack('<2Q',0x20000,0x21000),
            0x21004:struct.pack('<i',1),0x20000:struct.pack('<Q',0x30000),0x30000:struct.pack('<Q',0x40000),
            0x400f0:struct.pack('<Q',getter),0x30080:struct.pack('<4f',12,13,14,1)}
        def read(address,size):
            value=data[address];self.assertEqual(len(value),size);return value
        return data,read

    def test_live_vehicle_and_unsupported_getter_are_distinct(self):
        data,read=self.fixture();self.assertEqual(read_ride(read,0)['position'],[12,13,14])
        data[0x400f0]=struct.pack('<Q',0x123456)
        self.assertEqual(read_ride(read,0)['status'],'unsupported_transform')

    def test_expired_reference_never_dereferences_old_vehicle(self):
        data,read=self.fixture();data[0x21004]=struct.pack('<i',0);del data[0x20000]
        self.assertEqual(read_ride(read,0)['status'],'expired_weak_reference')
