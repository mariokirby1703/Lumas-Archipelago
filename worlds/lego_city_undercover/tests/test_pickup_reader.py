from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from pickup_reader import pickup_bit


class NativePickupIdentityTests(unittest.TestCase):
    def test_independently_observed_tile_sequences(self):
        self.assertEqual(pickup_bit(8,22,38,0),6752)
        self.assertEqual(pickup_bit(9,2,38,3),683)
        self.assertEqual(pickup_bit(7,8,38,0),2488)
        self.assertEqual(pickup_bit(6,3,38,0),960)

    def test_noncity_sentinel_and_invalid_ordinal_rejected(self):
        for args in ((255,255,38,0),(8,2,38,255),(8,2,38,8),(8,2,0,1)):
            with self.assertRaises(ValueError):pickup_bit(*args)
