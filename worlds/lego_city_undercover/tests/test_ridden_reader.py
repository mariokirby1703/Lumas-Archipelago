import struct
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from ridden_reader import read_ridden


class RiddenReaderTests(unittest.TestCase):
    def test_live_relation_and_unreviewed_getter_are_distinct(self):
        data={0x1c7d3e0:struct.pack('<Q',0x10000),0x10340:struct.pack('<Q',0x20000),
              0x20088:struct.pack('<Q',0x30000),0x30000:struct.pack('<Q',0x40000),
              0x40240:struct.pack('<Q',0x1f8830),0x30020:struct.pack('<Q',0x50000),
              0x50010:struct.pack('<Q',0x60000),0x600f0:struct.pack('<Q',0x49ecf0),
              0x501f0:struct.pack('<4f',11,12,13,1)}
        def read(address,size):
            value=data[address];self.assertEqual(len(value),size);return value
        result=read_ridden(read,0)
        self.assertEqual(result['position'],[11,12,13])
        self.assertEqual(result['species'],'not_inferred')
        data[0x40240]=struct.pack('<Q',0x123456)
        self.assertEqual(read_ridden(read,0)['status'],'unreviewed_ridden_accessor')
        data[0x40240]=struct.pack('<Q',0x1f8830)
        data[0x30020]=struct.pack('<Q',0)
        self.assertEqual(read_ridden(read,0)['status'],'not_riding')
