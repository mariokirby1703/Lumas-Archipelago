import importlib.util
from pathlib import Path
import struct
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from pickup_catalogue import parse_pickups


class PickupTests(unittest.TestCase):
    def sample(self, xyz=(1.0, 2.0, 3.0)):
        name = b"j_pup01\0"
        return (struct.pack("<II", 14, 1) + bytes(28)
                + struct.pack("<IhIB", 0x176, -1, 7, len(name)) + name
                + struct.pack("<3f", *xyz) + bytes(10))

    def test_type_flags_and_coordinates(self):
        row, = parse_pickups(self.sample())
        self.assertEqual((row["type_word"], row["type_code"]), (0x176, 0x76))
        self.assertEqual(row["resource_xyz"], [1, 2, 3])
        self.assertEqual(row["name"], "j_pup01")
        self.assertEqual(row["reference"], -1)

    def test_parent_extension_preserves_following_record(self):
        first=self.sample()[:-10]+bytes(8)+bytes((1,7))+b'Parent\0'+struct.pack('<3f',0.1,0.2,0.3)+b'\0'
        data=first+self.sample()[36:]
        data=data[:4]+struct.pack('<I',2)+data[8:]
        rows=parse_pickups(data)
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['parent']['name'],'Parent')
        self.assertEqual(rows[1]['name'],'j_pup01')
        with self.assertRaises(ValueError):parse_pickups(data[:-5])

    def test_truncation_and_unknown_extensions_rejected(self):
        data = self.sample()
        for truncated in (data[:7], data[:36], data[:-1], data + b"\0"):
            with self.assertRaises(ValueError):
                parse_pickups(truncated)

    def test_nonfinite_and_wrong_version_rejected(self):
        for data in (self.sample((float("nan"), 0, 0)), b"\x0c" + self.sample()[1:]):
            with self.assertRaises(ValueError):
                parse_pickups(data)

    def test_v13_three_byte_type(self):
        old=self.sample()
        data=struct.pack('<I',13)+old[4:39]+old[40:]
        row,=parse_pickups(data)
        self.assertEqual(row['type_word'],0x176)
        self.assertEqual(row['name'],'j_pup01')


if __name__ == "__main__":
    unittest.main()
