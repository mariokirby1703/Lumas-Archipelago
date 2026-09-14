import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ..client.constants import MANAGER_PTR, RESULT_VTABLE, ROOT_SUB
from ..client.journal import Journal
from ..client.memory import Memory, MemoryUnavailable
from ..client.runtime import Runtime
from ..data import MINIGAMES
from ..Items import (BARKER_COIN, COIN_BUNDLE_DATA, COIN_TRAP_DATA, ITEM_TABLE, UNLOCKS,
                     coin_bundle_name, coin_trap_name)
from .test_world import generate


class FakeDolphin:
    def __init__(self):
        self.ram = {}
        self.writes = []

    def read_bytes(self, address, size):
        return bytes(self.ram.get(address+i, 0) for i in range(size))

    def write_bytes(self, address, data):
        self.writes.append((address, data))
        self.ram.update({address+i: byte for i, byte in enumerate(data)})


class TestRuntime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'journal.json'
        self.backend = FakeDolphin()
        self.memory = Memory(self.backend)
        self.manager, self.root, self.session = 0x805F5400, 0x8094E72C, 0x80900000
        self.sub = self.root + ROOT_SUB
        self.controller, self.hole_state, self.hole_def = 0x80910000, 0x80920000, 0x80930000
        for address, value in ((MANAGER_PTR, self.manager), (self.manager+0x12C, 1),
                               (self.manager+0x190, self.root), (self.manager+0x114, self.session),
                               (self.manager+0x10C, self.hole_def), (self.session+0xFC, self.controller),
                               (self.root+0x19C, self.hole_state), (self.hole_def+0x0C, 3),
                               (self.controller+0x1C, 0x80400000)):
            self.memory.put(address, value, 4)
        self.backend.writes.clear()
        self.slot = generate(dict(starting_world=1, hole_in_one_checks=1, minigame_checks=3)).worlds[1].fill_slot_data()
        self.runtime = Runtime(self.slot, Journal(self.path))
        verify = patch.object(self.memory, 'verify_game', return_value=True)
        verify.start()
        self.addCleanup(verify.stop)

    def poll(self, items=()):
        return self.runtime.poll(self.memory, items)

    def test_invalid_game_and_pointers_never_write(self):
        with patch.object(self.memory, 'verify_game', return_value=False):
            with self.assertRaises(MemoryUnavailable):
                self.poll()
        self.assertFalse(self.backend.writes)
        self.memory.put(self.manager+0x190, 0, 4)
        self.backend.writes.clear()
        with self.assertRaises(MemoryUnavailable):
            self.poll()
        self.assertFalse(self.backend.writes)

    def test_big_endian_and_coin_receipts_reconnect(self):
        self.memory.put(self.sub+0x58, 0x1234, 2)
        self.assertEqual(self.memory.read(self.sub+0x58, 2), b'\x12\x34')
        items = [ITEM_TABLE[coin_bundle_name(0, 100)], ITEM_TABLE[BARKER_COIN]]
        self.poll(items)
        self.assertEqual(self.memory.integer(self.sub+0x58, 2), 0x1234+100)
        self.assertEqual(self.memory.integer(self.sub+0x85, 1), 1)
        self.runtime = Runtime(self.slot, Journal(self.path))
        self.poll(items)
        self.assertEqual(self.memory.integer(self.sub+0x58, 2), 0x1234+100)
        self.assertEqual(self.memory.integer(self.sub+0x85, 1), 1)
        self.memory.put(self.sub+0x58, 65530, 2)
        self.poll(items + [ITEM_TABLE[coin_bundle_name(0, 100)]])
        self.assertEqual(self.memory.integer(self.sub+0x58, 2), 65535)

    def test_interrupted_currency_transaction(self):
        journal = self.runtime.journal
        journal.data['pending'] = dict(index=0, offset=0x58, size=2, before=0, after=100)
        journal.save()
        self.memory.put(self.sub+0x58, 100, 2)
        self.poll([ITEM_TABLE[coin_bundle_name(0, 100)]])
        self.assertEqual(self.memory.integer(self.sub+0x58, 2), 100)
        self.assertEqual(journal.data['cursor'], 1)

    def test_ambiguous_currency_transaction(self):
        journal = self.runtime.journal
        journal.data['pending'] = dict(index=0, offset=0x58, size=2, before=0, after=100)
        self.memory.put(self.sub+0x58, 50, 2)
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            self.poll([ITEM_TABLE[coin_bundle_name(0, 100)]])
        self.assertEqual(self.memory.integer(self.sub+0x58, 2), 50)

    def test_every_bundle_amount_and_world(self):
        items = []
        expected = [0]*9
        for name, (world, amount) in COIN_BUNDLE_DATA.items():
            with self.subTest(world=world, amount=amount):
                items.append(ITEM_TABLE[name])
                expected[world] += amount
                self.poll(items)
                self.assertEqual([self.memory.integer(self.sub+0x58+2*w, 2) for w in range(9)], expected)

    def test_every_trap_amount_and_world_clamps_at_zero(self):
        for world in range(9):
            self.memory.put(self.sub+0x58+2*world, 60, 2)
        items = []
        expected = [60]*9
        for name, (world, amount) in COIN_TRAP_DATA.items():
            with self.subTest(world=world, amount=amount):
                items.append(ITEM_TABLE[name])
                expected[world] = max(0, expected[world] - amount)
                self.poll(items)
                self.assertEqual([self.memory.integer(self.sub+0x58+2*w, 2) for w in range(9)], expected)
        self.assertEqual(expected, [0]*9)

    def test_trap_reconnect_does_not_deduct_twice(self):
        self.memory.put(self.sub+0x58, 100, 2)
        items = [ITEM_TABLE[coin_trap_name(0, 50)]]
        self.poll(items)
        self.assertEqual(self.memory.integer(self.sub+0x58, 2), 50)
        self.runtime = Runtime(self.slot, Journal(self.path))
        self.poll(items)
        self.assertEqual(self.memory.integer(self.sub+0x58, 2), 50)

    def test_locks_all_local_players_and_vanilla_reassertion(self):
        second = 0x80950000
        self.memory.put(self.manager+0x12C, 2, 4)
        self.memory.put(self.manager+0x194, second, 4)
        for root in (self.root, second):
            self.memory.write(root+0x2CC, bytes(9))
        self.poll([ITEM_TABLE[UNLOCKS[4]]])
        expected = bytes([0, 1, 1, 1, 0, 1, 1, 1, 1])
        for root in (self.root, second):
            self.assertEqual(self.memory.read(root+0x2CC, 9), expected)
        self.memory.put(second+0x2CD, 0)
        self.poll([ITEM_TABLE[UNLOCKS[4]]])
        self.assertEqual(self.memory.read(second+0x2CC, 9), expected)

    def test_persistent_prizes_and_par_exact_one(self):
        self.memory.put(self.sub+80, 2)
        self.memory.put(self.sub+0x86, 1)
        self.memory.put(self.sub+0x6A, 1)
        checks = self.poll()
        self.assertNotIn(self.runtime.lookup['secret', 80], checks)
        self.assertIn(self.runtime.lookup['par', 0], checks)
        self.assertIn(self.runtime.lookup['barker', 0], checks)
        self.memory.put(self.sub+80, 1)
        self.assertIn(self.runtime.lookup['secret', 80], self.poll())
        self.runtime = Runtime(self.slot, Journal(self.path))
        self.assertIn(self.runtime.lookup['secret', 80], self.poll())

    def test_hio_edge_and_stale_attach(self):
        self.memory.put(self.hole_state+0x127, 1)
        self.memory.put(self.root+0x2DC, 1, 4)
        self.assertNotIn(self.runtime.lookup['hio', 0], self.poll())
        self.memory.put(self.hole_state+0x127, 0)
        self.poll()
        self.memory.put(self.hole_state+0x127, 1)
        checks = self.poll()
        self.assertIn(self.runtime.lookup['hio', 0], checks)
        self.assertIn(self.runtime.lookup['par', 0], checks)

    def test_minigame_results_and_disabled_checks(self):
        self.memory.put(self.controller+0x1C, MINIGAMES[0][1], 4)
        self.memory.put(self.controller+0x44, self.root, 4)
        array, popup = 0x80960000, 0x80970000
        self.memory.put(self.manager+0x100, array, 4)
        self.poll()
        self.memory.put(self.manager+0x104, 1, 4)
        self.memory.put(array, popup, 4)
        self.memory.put(popup+0x1C, RESULT_VTABLE, 4)
        self.memory.write(popup+0xC0, bytes([1, 1]))
        checks = self.poll()
        self.assertIn(self.runtime.lookup['win', 0], checks)
        self.assertIn(self.runtime.lookup['perfect', 0], checks)
        other = generate(dict(starting_world=1, minigame_checks=2)).worlds[1].fill_slot_data()
        runtime = Runtime(other, Journal(Path(self.tmp.name)/'perfect.json'))
        self.assertNotIn(('win', 0), runtime.lookup)
        self.assertFalse(runtime.poll(self.memory, []))  # stale popup on attach

    def test_counter_final_world_and_victory(self):
        slot = generate(dict(starting_world=1, goal_world=2, barker_goal_world_requirement=1,
                             barker_coins_required=3)).worlds[1].fill_slot_data()
        self.runtime = Runtime(slot, Journal(self.path))
        items = [ITEM_TABLE[BARKER_COIN]]*2
        self.poll(items)
        self.assertEqual(self.memory.integer(self.root+0x2CD, 1), 1)
        self.assertFalse(self.runtime.victory(items, set()))
        items.append(ITEM_TABLE[BARKER_COIN])
        self.poll(items)
        self.assertEqual(self.memory.integer(self.root+0x2CD, 1), 0)
        self.assertEqual(self.memory.integer(self.sub+0x85, 1), 3)
        self.memory.put(self.sub+0x85, 0)
        self.poll(items)
        self.assertEqual(self.memory.integer(self.sub+0x85, 1), 3)
        self.assertFalse(self.runtime.victory(items, set()))
        for i in range(3, 6):
            self.memory.put(self.sub+0x86+i, 1)
        self.assertTrue(self.runtime.victory(items, self.poll(items)))

    def test_all_par_goal_and_hunt(self):
        checks = {self.runtime.lookup['par', i] for i in range(27)}
        self.assertTrue(self.runtime.victory([], checks))
        checks.remove(self.runtime.lookup['par', 26])
        self.assertFalse(self.runtime.victory([], checks))
        slot = generate(dict(goal=1, barker_coins_required=2)).worlds[1].fill_slot_data()
        runtime = Runtime(slot, Journal(self.path))
        self.assertFalse(runtime.victory([ITEM_TABLE[BARKER_COIN]], set()))
        self.assertTrue(runtime.victory([ITEM_TABLE[BARKER_COIN]]*2, set()))
