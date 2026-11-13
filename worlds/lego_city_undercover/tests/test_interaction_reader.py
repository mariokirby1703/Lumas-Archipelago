from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from interaction_reader import (read_interaction, InteractionTracker, interaction_text,
                                scene_fields_text, immediate_proximity)


class InteractionTests(unittest.TestCase):
    def fixture(self, flags=0x110100, player=(1., 2., 3.)):
        base, manager, target, actor = 0x140000000, 0x20000, 0x30000, 0x40000
        data = bytearray(0x250)
        struct.pack_into('<Q', data, 0, base + 0xC34578)
        name = b'#cg_433_BNE_STEELDOOR_SW\0'
        data[0x58:0x58+len(name)] = name
        struct.pack_into('<3f', data, 0x78, 1., 2., 3.)
        struct.pack_into('<3f', data, 0x22c, 1., 2., 3.)
        struct.pack_into('<I', data, 0x24c, flags)
        memory = {base+0x17ec098: struct.pack('<Q', manager),
                  manager: struct.pack('<Q', base+0xc34ae8),
                  manager+0x110: struct.pack('<Qfi', target, 0., 3), target: bytes(data),
                  manager+0x11c: struct.pack('<i', 3),
                  base+0x1c7d3e0: struct.pack('<Q', actor),
                  actor+0x1f0: struct.pack('<3f', *player)}
        return base, memory, lambda a, n: memory[a][:n]

    def test_observed_door_uses_category_not_explicit_crowbar_bit(self):
        base, _, read = self.fixture()
        state = read_interaction(read, base)
        self.assertEqual(state['family'], 'Brechstangentür')
        self.assertFalse(state['explicit_crowbar_item_bit'])
        self.assertTrue(state['robber_class_requirement_bit'])
        self.assertIsNone(state['locked'])
        self.assertEqual(state['native_selection_result'], 3)
        self.assertFalse(state['field_under_player_verified'])

    def test_retained_distant_target_is_not_underfoot(self):
        base, _, read = self.fixture(player=(100., 2., 3.))
        state = read_interaction(read, base)
        self.assertFalse(state['nearby'])
        self.assertFalse(state['immediate_proximity'])
        self.assertIn('Kein ausgewähltes Feld', interaction_text(state))

    def test_other_floor_and_distant_scene_objects_hidden_by_default(self):
        self.assertFalse(immediate_proximity((0., 1., 0.), (0., 2., 0.)))
        self.assertFalse(immediate_proximity((2., 2., 0.), (0., 2., 0.)))
        self.assertTrue(immediate_proximity((0.05, 2., 0.), (0., 2., 0.)))
        common = dict(family='Tastenfeld', distance=.05)
        state = dict(status='read', fields=[dict(common, name='KEYPAD', immediate_proximity=True),
                                           dict(common, name='SAFE_OTHER_FLOOR', immediate_proximity=False)])
        self.assertNotIn('SAFE_OTHER_FLOOR', scene_fields_text(state))
        self.assertIn('KEYPAD', scene_fields_text(state))
        self.assertIn('SAFE_OTHER_FLOOR', scene_fields_text(state, show_all=True))

    def test_missing_and_unknown_layout_do_not_guess(self):
        base, memory, read = self.fixture()
        memory[0x20000+0x110] = bytes(16)
        self.assertEqual(read_interaction(read, base)['status'], 'no_candidate')
        memory[0x20000+0x110] = struct.pack('<Qfi', 0x30000, 0., 3)
        memory[0x30000] = bytes(0x250)
        self.assertEqual(read_interaction(read, base)['status'], 'unresolved')

    def test_history_ignores_position_jitter_but_records_loss(self):
        base, _, read = self.fixture()
        state = read_interaction(read, base)
        tracker = InteractionTracker()
        self.assertTrue(tracker.update(state)['initial'])
        self.assertIsNone(tracker.update(dict(state, distance=.1)))
        self.assertIsNotNone(tracker.update(dict(status='no_candidate')))
        self.assertIsNotNone(tracker.update(state))
