import struct
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from menu_flow_reader import parse_page_table

class MenuFlowReaderTests(unittest.TestCase):
    def test_supported_table_and_invalid_native_counts(self):
        self.assertEqual(parse_page_table(struct.pack('<Qii',4096,44,44)),(4096,44))
        for pointer,capacity,count in ((0,44,44),(4096,43,44),(4096,129,44),(4096,44,-1),(4096,44,45)):
            with self.assertRaises(ValueError):parse_page_table(struct.pack('<Qii',pointer,capacity,count))
        with self.assertRaises(ValueError):parse_page_table(bytes(15))
