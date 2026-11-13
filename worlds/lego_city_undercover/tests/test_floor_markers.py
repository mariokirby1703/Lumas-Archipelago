from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from floor_markers import predict_floor_marker


class FloorMarkerTests(unittest.TestCase):
    def test_door_safe_and_axe_use_distinct_available_and_locked_markers(self):
        for flags, group, suffix, locked in (
                (0x110100, 1, 'Robber_Crowbar', 'Robber_Locked'),
                (0x100002, 1, 'Robber_Stethoscope', 'Robber_Locked'),
                (0x110200, 5, 'Fireman_Axe', 'Fireman_Locked')):
            unlocked = predict_floor_marker(flags, {group: True})
            self.assertTrue(unlocked['predicted_marker'].endswith(suffix))
            self.assertFalse(unlocked['rendered_state_verified'])
            self.assertTrue(predict_floor_marker(flags, {group: False})['predicted_marker'].endswith(locked))

    def test_branch_order_and_separate_tool_ability(self):
        # Police/scanner flag takes precedence over robber bit.
        self.assertEqual(predict_floor_marker(0x110, {0:True, 1:True})['required_class'], 'Polizist')
        state = predict_floor_marker(0x80000, {1:True}, {'EnergyGun':False})
        self.assertTrue(state['class_lock_candidate'])
        self.assertEqual(state['required_ability'], 'EnergyGun')
        self.assertTrue(predict_floor_marker(0x80000, {1:True}, {'EnergyGun':True})['predicted_marker'].endswith('EnergyGun'))

    def test_missing_inputs_never_imply_unlocked_and_generic_fallback_stays_unknown(self):
        self.assertIsNone(predict_floor_marker(0x100)['predicted_marker'])
        self.assertIsNone(predict_floor_marker(0)['predicted_marker'])
        self.assertTrue(predict_floor_marker(0x80000000, custom_icon=641)['predicted_marker'].endswith('Keycard'))
