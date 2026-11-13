from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from aura_reader import read_auras, name_hash, AuraTracker, aura_text


class AuraTests(unittest.TestCase):
    def fixture(self, type_name='DetectiveMode'):
        base, manager, state, actor, player = 0x140000000, 0x20000, 0x30000, 0x40000, 0x50000
        node, definition = 0x60000, 0x70000
        root = player + 0x990
        data = bytearray(0x70)
        struct.pack_into('<Q', data, 0x20, definition)
        struct.pack_into('<3f', data, 0x30, 1., 2., 3.)
        struct.pack_into('<I', data, 0x60, 123)
        memory = {base+0x17ebc90: struct.pack('<Q', manager),
                  manager+0x138: struct.pack('<Q', state),
                  base+0x1c7d3e0: struct.pack('<Q', actor), actor+0x3e3: b'\0',
                  state+0x1770: struct.pack('<Q', player),
                  root: struct.pack('<Q', base+0xc7f028),
                  root+0x38: struct.pack('<Q', node), node: bytes(data),
                  definition: struct.pack('<I', 0x10001),
                  definition+0x38: struct.pack('<Q', 0x71000),
                  0x71000: type_name.encode('ascii') + bytes(64-len(type_name))}
        return base, memory, lambda a, n: memory[a][:n]

    def test_native_types_are_separate_from_occupancy_and_permission(self):
        for name, label in [('DetectiveMode', 'Detektivscan'), ('AudioScan', 'Gesprächsscan'),
                            ('CriminalScan', 'Personen-/Kriminellenscan')]:
            base, _, read = self.fixture(name)
            marker = read_auras(read, base)['markers'][0]
            self.assertEqual(marker['type'], label)
            self.assertIsNone(marker['inside'])
            self.assertIsNone(marker['locked'])
            self.assertEqual(marker['native_id'], 123)

    def test_empty_registry_does_not_assert_no_aura(self):
        base, memory, read = self.fixture()
        memory[0x50000+0x990+0x38] = bytes(8)
        state = read_auras(read, base)
        self.assertEqual(state['markers'], [])
        self.assertFalse(state['occupancy_verified'])
        self.assertIn('unbestätigt', aura_text(state))

    def test_unknown_marker_and_cycle_are_not_misclassified(self):
        base, memory, read = self.fixture('UnrecognizedType')
        self.assertFalse(read_auras(read, base)['markers'][0]['recognized_scan_type'])
        data = bytearray(memory[0x60000]);struct.pack_into('<Q', data, 0x10, 0x60000)
        memory[0x60000] = bytes(data)
        with self.assertRaises(ValueError):
            read_auras(read, base)

    def test_history_records_registry_loss_and_reentry(self):
        base, _, read = self.fixture()
        state = read_auras(read, base)
        tracker = AuraTracker()
        self.assertTrue(tracker.update(state)['initial'])
        self.assertIsNone(tracker.update(state))
        self.assertIsNotNone(tracker.update(dict(status='unresolved', reason='loading')))
        self.assertIsNotNone(tracker.update(state))
