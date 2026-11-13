from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from interaction_reader import read_scene_fields, SceneFieldTracker
from scene_reader import player_scene


class SceneFieldsTests(unittest.TestCase):
    def fixture(self):
        base = 0x140000000
        component, actor, obj, techno = 0x20000, 0x30000, 0x40000, 0x50000
        data = bytearray(0x400)
        struct.pack_into('<Q', data, 0, base+0xc34578)
        struct.pack_into('<Q', data, 0x48, component)
        name = b'#cg_442_SAFE_HIGH_SW\0'
        data[0x58:0x58+len(name)] = name
        struct.pack_into('<3f', data, 0x22c, 1., 2., 3.)
        struct.pack_into('<I', data, 0x24c, 0x100002)
        memory = {component: struct.pack('<Q', base+0xc34ed8),
                  component+0xe0: struct.pack('<Q', obj),
                  techno: struct.pack('<Q', base+0xc36198), techno+0xe0: bytes(8),
                  actor+0x1f0: struct.pack('<3f', 1., 2., 3.), obj: data}
        def read(a, n):
            for start, value in memory.items():
                if start <= a and a+n <= start+len(value):
                    return bytes(value[a-start:a-start+n])
            raise OSError('Unmapped test address')
        scene = dict(actor=actor, level=0x60000, table=0x70000)
        return base, memory, read, scene

    def test_loaded_safe_is_not_assumed_usable_or_underfoot(self):
        base, _, read, scene = self.fixture()
        with patch('interaction_reader.player_scene', return_value=scene), patch(
                'interaction_reader.scene_component', side_effect=[0x20000, 0x50000]):
            state = read_scene_fields(read, base)
        row = state['fields'][0]
        self.assertEqual(row['family'], 'Tresor / Stethoskop')
        self.assertEqual(row['distance'], 0.)
        self.assertIsNone(row['locked'])
        self.assertFalse(row['under_player_verified'])
        tracker = SceneFieldTracker()
        self.assertTrue(tracker.update(state)['initial'])
        self.assertIsNone(tracker.update(state))
        self.assertIsNotNone(tracker.update(dict(status='unresolved', reason='scene loading')))

    def test_scene_change_and_cyclic_objects_are_rejected(self):
        base, memory, read, scene = self.fixture()
        with patch('interaction_reader.player_scene', side_effect=[scene, dict(scene, level=0x80000)]), patch(
                'interaction_reader.scene_component', side_effect=[0x20000, 0x50000]):
            with self.assertRaises(RuntimeError):
                read_scene_fields(read, base)
        struct.pack_into('<Q', memory[0x40000], 0x28, 0x40000)
        with patch('interaction_reader.player_scene', return_value=scene), patch(
                'interaction_reader.scene_component', return_value=0x20000):
            with self.assertRaises(ValueError):
                read_scene_fields(read, base)

    def test_scene_resolution_uses_native_entity_id_not_actor_owner_guess(self):
        base = 0x140000000
        def q(value): return struct.pack('<Q', value)
        memory = {base+0x1c7d3e0:q(0x20000), 0x20010:q(0x30000),
                  0x30010:q(base+0x487160), 0x20028:struct.pack('<H', 4),
                  base+0x1c402d8:q(0x40000), 0x40038:q(0x50000),
                  0x500d8:q(0x60000), 0x60b18:q(1), 0x60bb0:q(0x70000),
                  0x700a0:q(0x80000), 0x800c0:q(0x90000)}
        scene = player_scene(lambda a,n:memory[a][:n], base)
        self.assertEqual(scene, dict(actor=0x20000, level=0x70000, table=0x90000))
