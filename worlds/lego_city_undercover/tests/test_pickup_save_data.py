from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from pickup_save_data import extract_section, set_bits, SECTION_HASH, PAYLOAD_SIZE


class PickupSaveTests(unittest.TestCase):
    def sample(self):
        return struct.pack("<II", SECTION_HASH, PAYLOAD_SIZE) + bytes(PAYLOAD_SIZE) + struct.pack("<I", SECTION_HASH)

    def test_bounded_named_section(self):
        self.assertEqual(extract_section(b"prefix" + self.sample()), (14, bytes(PAYLOAD_SIZE)))

    def test_missing_truncated_and_ambiguous_rejected(self):
        for data in (b"", self.sample()[:-1], self.sample() + self.sample()):
            with self.assertRaises(ValueError):
                extract_section(data)

    def test_bit_offsets_and_size(self):
        payload = bytearray(PAYLOAD_SIZE)
        payload[654], payload[694] = 56, 4
        self.assertEqual(set_bits(payload), [5235, 5236, 5237, 5554])
        with self.assertRaises(ValueError):
            set_bits(payload[:-1])
