import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from probe_native_district import grid_coordinates


class NativeGridTests(unittest.TestCase):
    def test_both_user_confirmed_bluebell_positions(self):
        for position in ((-217.1602478, 13.71088, 300.339386), (-220.6271973, 13.70877, 303.264008)):
            self.assertEqual(grid_coordinates(position, (-450, 0, 450), 30, -1, 38, 38), (7, 4))

    def test_bounds_and_bad_transform(self):
        for position, size in (((10000, 0, 0), 30), ((0, 0, 0), 0), ((float('nan'), 0, 0), 30)):
            with self.assertRaises(ValueError):
                grid_coordinates(position, (-450, 0, 450), size, -1, 38, 38)
