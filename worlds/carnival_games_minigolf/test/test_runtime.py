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
                     GOAL_WORLD_ACCESS, PAR_CLUB_PIECES, coin_bundle_name, coin_trap_name)
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
        self.slot = generate(dict(starting_world=0, hole_in_one_checks=1, minigame_checks=3)).worlds[1].fill_slot_data()
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

    def test_resolver_uses_configured_profile_and_tolerates_empty_menu_slots(self):
        self.memory.put(self.manager+0x194, 0, 4)
        snapshot = self.memory.resolve(0)
        self.assertEqual(snapshot.root, self.root)
        self.assertEqual(snapshot.roots, (self.root,))
        self.memory.put(self.manager+0x114, 0, 4)
        with self.assertRaisesRegex(MemoryUnavailable, 'configured game player state'):
            self.memory.resolve(1)
        with self.assertRaisesRegex(MemoryUnavailable, 'Waiting for game player state'):
            self.memory.put(self.manager+0x190, 0, 4)
            self.memory.resolve(1)
        self.backend.writes.clear()
        with self.assertRaises(MemoryUnavailable):
            self.poll()
        self.assertFalse(self.backend.writes)

    def test_session_field_does_not_override_configured_profile(self):
        second = 0x80950000
        self.memory.put(self.manager+0x194, second, 4)
        self.memory.put(self.session+0x2EC, 1, 4)
        snapshot = self.memory.resolve(0)
        self.assertEqual(snapshot.root, self.root)
        self.assertEqual(snapshot.local_player, 0)
        self.assertEqual(snapshot.requested_player, 0)

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

    def test_mem2_addresses_are_read_without_translation_by_the_wrapper(self):
        address = 0x927F99D4
        self.memory.put(address, 0x12345678, 4)
        self.assertEqual(self.memory.integer(address), 0x12345678)

    def test_failed_mem2_live_read_keeps_persistent_sync_running(self):
        original_read = self.backend.read_bytes

        def fail_live_goal_read(address, size):
            if address == self.hole_state + 0x127:
                raise RuntimeError("Could not read memory")
            return original_read(address, size)

        self.memory.put(self.sub+48, 1)
        self.backend.read_bytes = fail_live_goal_read
        checks = self.poll()
        self.assertIn(self.runtime.lookup['shop', 48], checks)
        expected_locks = bytes(0 if i == self.slot['starting_world'] else 1 for i in range(9))
        self.assertEqual(self.memory.read(self.root+0x2CC, 9), expected_locks)
        self.assertIsNone(self.runtime.previous_hole)

    def test_failed_live_read_preserves_existing_hole_edge_state(self):
        self.memory.put(self.hole_state+0x127, 0)
        self.poll()
        previous = self.runtime.previous_hole
        original_read = self.backend.read_bytes

        def fail_once(address, size):
            if address == self.hole_state + 0x127:
                self.backend.read_bytes = original_read
                raise RuntimeError("Could not read memory")
            return original_read(address, size)

        self.backend.read_bytes = fail_once
        self.poll()
        self.assertEqual(self.runtime.previous_hole, previous)
        self.memory.put(self.hole_state+0x127, 1)
        self.assertIn(self.runtime.lookup['complete', 0], self.poll())

    def test_detected_check_is_journaled_before_later_context_failure(self):
        self.memory.put(self.hole_state+0x127, 0)
        self.poll()
        self.memory.put(self.hole_state+0x127, 1)
        check = self.runtime.lookup['complete', 0]
        with patch.object(self.memory, 'confirm', side_effect=MemoryUnavailable('context changed')):
            with self.assertRaises(MemoryUnavailable):
                self.poll()
        self.assertIn(check, self.runtime.journal.data['checks'])

    def test_interrupted_currency_transaction(self):
        journal = self.runtime.journal
        journal.data['pending'] = dict(index=0, offset=0x58, size=2, before=0, after=100)
        journal.save()
        self.memory.put(self.sub+0x58, 100, 2)
        self.poll([ITEM_TABLE[coin_bundle_name(0, 100)]])
        self.assertEqual(self.memory.integer(self.sub+0x58, 2), 100)
        self.assertEqual(journal.data['cursor'], 1)

    def test_incomplete_item_history_only_gates_inventory_writes(self):
        item = ITEM_TABLE[coin_bundle_name(0, 100)]
        self.runtime.journal.data['cursor'] = 4
        self.runtime.journal.save()
        self.memory.put(self.sub+48, 1)
        checks = self.runtime.poll(self.memory, [item], history_ready=False)
        self.assertIn(self.runtime.lookup['shop', 48], checks)
        self.assertEqual(self.memory.integer(self.sub+0x58, 2), 0)
        expected_locks = bytes(0 if i == self.slot['starting_world'] else 1 for i in range(9))
        self.assertEqual(self.memory.read(self.root+0x2CC, 9), expected_locks)
        with self.assertRaisesRegex(MemoryUnavailable, 'complete AP received-item history'):
            self.runtime.poll(self.memory, [item], history_ready=True)

    def test_incomplete_history_does_not_project_partial_piece_inventory(self):
        self.memory.put(self.manager+0x114, 0, 4)
        item = ITEM_TABLE[PAR_CLUB_PIECES[0]]
        self.runtime.poll(self.memory, [item], history_ready=False)
        self.assertEqual(self.memory.read(self.sub+0x86, 27), bytes(27))

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

    def test_persistent_prizes_reconcile_but_par_does_not(self):
        self.memory.put(self.sub+80, 2)
        self.memory.put(self.sub+0x86, 1)
        self.memory.put(self.sub+0x6A, 1)
        checks = self.poll()
        self.assertNotIn(self.runtime.lookup['secret', 80], checks)
        self.assertNotIn(self.runtime.lookup['par', 0], checks)
        self.assertIn(self.runtime.lookup['barker', 0], checks)
        self.memory.put(self.sub+80, 1)
        self.assertIn(self.runtime.lookup['secret', 80], self.poll())
        self.runtime = Runtime(self.slot, Journal(self.path))
        self.assertIn(self.runtime.lookup['secret', 80], self.poll())

    def test_shop_purchase_is_reconciled_after_missed_transition_and_reconnect(self):
        # Prize 48 is a Rah's Revenge shop entry in the starting world.
        self.poll()
        self.memory.put(self.sub+48, 1)
        check = self.runtime.lookup['shop', 48]
        self.assertIn(check, self.poll())
        self.runtime = Runtime(self.slot, Journal(self.path))
        self.assertIn(check, self.poll())

    def test_shop_checks_only_scan_configured_root_without_session(self):
        second = 0x80950000
        self.memory.put(self.manager+0x12C, 2, 4)
        self.memory.put(self.manager+0x194, second, 4)
        self.memory.put(self.manager+0x114, 0, 4)
        self.memory.put(second+ROOT_SUB+48, 1)
        self.backend.writes.clear()
        self.assertNotIn(self.runtime.lookup['shop', 48], self.poll())
        self.memory.put(self.sub+48, 1)
        self.assertIn(self.runtime.lookup['shop', 48], self.poll())

    def test_persistent_check_is_sent_even_when_its_world_is_locked(self):
        # Prize 65 belongs to Amazeon, which is locked in this starting-world fixture.
        self.memory.put(self.sub+65, 1)
        self.assertIn(self.runtime.lookup['shop', 65], self.poll())

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
        self.assertIn(self.runtime.lookup['complete', 0], checks)

    def test_hole_check_is_sent_even_when_ap_world_is_locked(self):
        self.memory.put(self.session+0x2F0, 8, 4)
        self.memory.put(self.hole_state+0x127, 0)
        self.poll()
        self.memory.put(self.root+0x2DC, 3, 4)
        self.memory.put(self.hole_state+0x127, 1)
        checks = self.poll()
        self.assertIn(self.runtime.lookup['complete', 8], checks)
        self.assertIn(self.runtime.lookup['par', 8], checks)

    def test_minigame_results_and_disabled_checks(self):
        self.memory.put(self.controller+0x1C, MINIGAMES[0][1], 4)
        self.memory.put(self.controller+0x44, 0, 4)  # Not a universal owner field.
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
        other = generate(dict(starting_world=0, minigame_checks=2)).worlds[1].fill_slot_data()
        runtime = Runtime(other, Journal(Path(self.tmp.name)/'perfect.json'))
        self.assertNotIn(('win', 0), runtime.lookup)
        self.assertFalse(runtime.poll(self.memory, []))  # stale popup on attach

    def test_latched_minigame_survives_controller_change_for_result(self):
        self.memory.put(self.controller+0x1C, MINIGAMES[5][1], 4)
        array, popup = 0x80960000, 0x80970000
        self.memory.put(self.manager+0x100, array, 4)
        self.poll()
        self.memory.put(self.controller+0x1C, 0x80400000, 4)
        self.memory.put(self.manager+0x104, 1, 4)
        self.memory.put(array, popup, 4)
        self.memory.put(popup+0x1C, RESULT_VTABLE, 4)
        self.memory.write(popup+0xC0, bytes([1, 1]))
        checks = self.poll()
        self.assertIn(self.runtime.lookup['win', 5], checks)
        self.assertIn(self.runtime.lookup['perfect', 5], checks)

    def test_debug_state_reports_live_hole_and_minigame_context(self):
        self.memory.put(self.session+0x2F0, 8, 4)
        self.memory.put(self.root+0x2DC, 3, 4)
        self.memory.put(self.hole_def+0x0C, 3, 4)
        self.memory.put(self.controller+0x1C, MINIGAMES[5][1], 4)
        state = self.runtime.debug_state(self.memory)
        self.assertEqual(state['manager'], self.manager)
        self.assertEqual(state['manager_state'], 0)
        self.assertEqual(state['session'], self.session)
        self.assertEqual(state['root'], self.root)
        self.assertEqual((state['hole'], state['strokes'], state['par']), (8, 3, 3))
        self.assertEqual(state['hole_state'], self.hole_state)
        self.assertEqual(state['vtable'], MINIGAMES[5][1])
        self.assertEqual(state['minigame'], 5)

    def test_counter_final_world_and_victory(self):
        slot = generate(dict(starting_world=0, goal=1, goal_world=1, goal_world_access=1,
                             barker_coins_required=3)).worlds[1].fill_slot_data()
        self.runtime = Runtime(slot, Journal(self.path))
        items = [ITEM_TABLE[BARKER_COIN]]*2
        self.poll(items)
        self.assertEqual(self.memory.integer(self.root+0x2CD, 1), 1)
        self.assertFalse(self.runtime.victory(items, set()))
        items.append(ITEM_TABLE[BARKER_COIN])
        checks = self.poll(items)
        requirement = self.runtime.lookup['barker_requirement', 0]
        self.assertIn(requirement, checks)
        self.assertEqual(self.memory.integer(self.root+0x2CD, 1), 1)
        self.assertEqual(self.memory.integer(self.sub+0x85, 1), 3)
        self.memory.put(self.sub+0x85, 0)
        self.poll(items)
        self.assertEqual(self.memory.integer(self.sub+0x85, 1), 3)
        self.assertFalse(self.runtime.victory(items, set()))
        items.append(ITEM_TABLE[GOAL_WORLD_ACCESS])
        self.poll(items)
        self.assertEqual(self.memory.integer(self.root+0x2CD, 1), 0)
        par_checks = {self.runtime.lookup['par', i] for i in range(3, 6)}
        self.assertTrue(self.runtime.victory(items, par_checks))

    def test_all_holes_goal_and_hunt(self):
        checks = {self.runtime.lookup['complete', i] for i in range(27)}
        self.assertTrue(self.runtime.victory([], checks))
        checks.remove(self.runtime.lookup['complete', 26])
        self.assertFalse(self.runtime.victory([], checks))
        slot = generate(dict(goal=2, barker_coins_required=2)).worlds[1].fill_slot_data()
        runtime = Runtime(slot, Journal(self.path))
        self.assertFalse(runtime.victory([ITEM_TABLE[BARKER_COIN]], set()))
        self.assertTrue(runtime.victory([ITEM_TABLE[BARKER_COIN]]*2, set()))

    def test_piece_projection_frontend_and_clear_during_play(self):
        items = [ITEM_TABLE[PAR_CLUB_PIECES[0]], ITEM_TABLE[PAR_CLUB_PIECES[0]],
                 ITEM_TABLE[PAR_CLUB_PIECES[2]]]
        # Independent dumps identify manager state 3 as the Pro Shop.
        self.memory.put(self.manager+0xBC, 3, 4)
        self.memory.put(self.manager+0x114, 0, 4)
        self.poll(items)
        expected = bytes([1, 1, 0, 0, 0, 0, 1, 0, 0] + [0] * 18)
        self.assertEqual(self.memory.read(self.sub+0x86, 27), expected)
        self.runtime.clear_piece_projection(self.memory)
        self.assertEqual(self.memory.read(self.sub+0x86, 27), bytes(27))
        self.poll(items)
        # Entering normal gameplay clears every projected and vanilla piece.
        self.memory.put(self.manager+0xBC, 5, 4)
        self.memory.put(self.manager+0x114, self.session, 4)
        self.memory.put(self.session+0x2F0, 0, 4)
        self.memory.write(self.sub+0x86, bytes([1])*27)
        self.poll(items)
        self.assertEqual(self.memory.read(self.sub+0x86, 27), bytes(27))

    def test_piece_projection_is_cleared_on_level_completion_screen(self):
        items = [ITEM_TABLE[PAR_CLUB_PIECES[6]]] * 2
        self.memory.put(self.manager+0xBC, 3, 4)
        self.memory.put(self.manager+0x114, 0, 4)
        self.poll(items)
        self.assertEqual(self.memory.read(self.sub+0x86+18, 3), bytes([1, 1, 0]))
        # The course ID can already be invalid while the result screen still owns
        # the live hole state. Never combine its Vanilla piece with AP pieces.
        self.memory.put(self.manager+0xBC, 6, 4)
        self.memory.put(self.manager+0x114, self.session, 4)
        self.memory.put(self.session+0x2F0, 99, 4)
        self.memory.put(self.hole_state+0x127, 1)
        self.memory.put(self.sub+0x86+20, 1)
        self.poll(items)
        self.assertEqual(self.memory.read(self.sub+0x86, 27), bytes(27))

    def test_par_check_survives_course_context_disappearing_with_received_piece(self):
        items = [ITEM_TABLE[PAR_CLUB_PIECES[0]]]
        self.memory.put(self.hole_state+0x127, 0)
        self.poll(items)
        self.assertEqual(self.memory.read(self.sub+0x86, 3), bytes(3))
        self.memory.put(self.root+0x2DC, 2, 4)
        self.memory.put(self.session+0x2F0, 99, 4)
        self.memory.put(self.hole_state+0x127, 1)
        checks = self.poll(items)
        self.assertIn(self.runtime.lookup['par', 0], checks)
        self.assertIn(self.runtime.lookup['complete', 0], checks)
        self.assertEqual(self.memory.read(self.sub+0x86, 27), bytes(27))
