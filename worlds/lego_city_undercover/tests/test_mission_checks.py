from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from mission_checks import completed_shield_locations, shield_locations, PARTS


class MissionShieldTests(unittest.TestCase):
    def test_whole_requires_four_distinct_parts(self):
        self.assertEqual(completed_shield_locations('SA1', 'whole', ['TL']*4), ())
        self.assertEqual(len(completed_shield_locations('SA1', 'whole', PARTS)), 1)

    def test_quarters_never_add_whole_check(self):
        self.assertEqual(len(shield_locations('SA1', 'quarters')), 4)
        result = completed_shield_locations('SA1', 'quarters', ['TL', 'BR'])
        self.assertEqual(result, ('SA1: Police Shield TL', 'SA1: Police Shield BR'))
        self.assertNotIn('SA1: Police Shield', completed_shield_locations('SA1', 'quarters', PARTS))

    def test_invalid_input_rejected(self):
        for mode in ('both', '', 'unknown'):
            with self.assertRaises(ValueError):
                shield_locations('SA1', mode)
        with self.assertRaises(ValueError):
            completed_shield_locations('SA1', 'quarters', ['unknown'])
