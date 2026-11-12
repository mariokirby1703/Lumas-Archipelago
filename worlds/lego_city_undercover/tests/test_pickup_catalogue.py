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

    def test_truncation_and_unknown_extensions_rejected(self):
        data = self.sample()
        for truncated in (data[:7], data[:36], data[:-1], data + b"\0"):
            with self.assertRaises(ValueError):
                parse_pickups(truncated)

    def test_nonfinite_and_wrong_version_rejected(self):
        for data in (self.sample((float("nan"), 0, 0)), b"\r" + self.sample()[1:]):
            with self.assertRaises(ValueError):
                parse_pickups(data)


if __name__ == "__main__":
    unittest.main()
