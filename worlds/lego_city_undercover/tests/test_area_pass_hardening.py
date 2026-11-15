"""Additional synthetic safety tests for the experimental area rollback controller.

These tests do not move the player in LEGO City Undercover and do not prove
that the native vehicle physics or streamed city transitions work in-game.
"""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from area_passes import (AreaGate, FIRST, START, FIRST_PASS_KEYS,
                         AUBURN_OPENING_KEYS, allowed_districts,
                         auburn_opening_key, canonical, has_area, tile_district)


class IdentityTests(unittest.TestCase):
    def test_auburn_is_free_without_any_pass(self):
        class Empty:
            def has(self, *args):
                return False
        self.assertEqual(allowed_districts([]), {START})
        self.assertTrue(has_area(Empty(), 1, 'SF_Docks'))
        self.assertFalse(has_area(Empty(), 1, FIRST))
        self.assertNotIn(START, allowed_districts([dict(category='area_pass', native_name=FIRST)] ) - {START})

    def test_canonical_districts_only_not_colliding_prefixes(self):
        cases = [
            ('SF_Docks_0918', 'SF_Docks'),
            ('NY_Downtown_East_1718', 'NY_Downtown_East'),
            ('NY_Downtown_1718', 'NY_Downtown'),
            ('NY_Monaco_Tunnel_1920', 'NY_Tunnel'),
            ('Police_Station_Lobby', None),
            ('SF_Residential_123', None),
            ('SF_Residential_12345', None),
            ('SF_Residential_12a4', None),
            (None, None),
        ]
        for tile, expected in cases:
            with self.subTest(tile=tile):
                self.assertEqual(tile_district(tile), expected)
        self.assertIsNone(canonical('SF_Docks_0918'))

    def test_area_receipts_are_distinct_from_other_items(self):
        receipts = [
            dict(category='character', name='Area Pass: SF_Residential'),
            dict(category='area_pass', name='Area Pass: sf_residential'),
            dict(category='area_pass', native_name='NY_Downtown_East'),
            dict(category='area_pass', native_name='unknown_region'),
        ]
        self.assertEqual(allowed_districts(receipts),
                         {'SF_Docks', 'SF_Residential', 'NY_Downtown_East'})

    def test_cherry_first_pass_cannot_be_placed_at_police_station(self):
        self.assertEqual(len(FIRST_PASS_KEYS), 3)
        self.assertTrue(FIRST_PASS_KEYS.issubset(AUBURN_OPENING_KEYS))
        self.assertTrue(auburn_opening_key('story_arrest:clown_1', {}))
        self.assertTrue(auburn_opening_key(
            'objective:DisguiseBooth_SF_DO_0918', dict(district='SF_Docks')))
        self.assertFalse(auburn_opening_key('story_disguise:COP', {}))
        self.assertFalse(auburn_opening_key(
            'source_pickup:GAME7/levels/standalones/police_station/test.giz:1:0',
            dict(source='GAME7/levels/standalones/police_station/test.giz')))
        self.assertFalse(auburn_opening_key(
            'source_pickup:GAME5/levels/lego_city/lego_city/sf_residential/test.giz:1:0',
            dict(district='SF_Residential')))


def _snap(area, context=46, scene=None, position=(0.0, 0.0, 0.0)):
    state = dict(
        actor=dict(status='read', context=dict(index=context)),
        location=dict(native_tile=area, player_position=position),
    )
    if scene is not None:
        state['mission_shield'] = dict(scene=scene)
    return state


class ControllerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.gate = AreaGate()
        self.session = SimpleNamespace(pid=101)
        self.journal = SimpleNamespace(binding_token=b'a' * 16)
        self.good = _snap('SF_Docks_0918')
        self.locked = _snap('SF_Residential_1022', position=(3, 0, 7))
        self.patcher = patch('native_model_transport.area_command',
                             return_value=dict(accepted=True, found=123))
        self.command = self.patcher.start()
        self.addCleanup(self.patcher.stop)

    async def poll(self, snapshot, backup=True, received=()):
        return await self.gate.poll(self.session, snapshot, self.journal,
                                    list(received), 'verified-dll.dll', backup_ready=backup)

    async def test_backup_required_and_no_unverified_checkpoint(self):
        self.assertEqual(await self.poll(self.good, backup=False),
                         'waiting_for_save_backup')
        self.command.assert_not_called()
        self.assertEqual(await self.poll(self.locked), 'locked_area_without_checkpoint')
        self.command.assert_not_called()
        self.assertIsNone(self.gate.checkpoint)

    async def test_mounted_checkpoint_captured_immediately_after_context_change(self):
        self.assertEqual(await self.poll(self.good), 'checkpoint_recorded')
        self.assertEqual(await self.poll(_snap('SF_Docks_0918', context=157)),
                         'checkpoint_recorded')
        self.assertEqual(self.gate.checkpoint_context, 157)
        self.assertEqual(self.command.call_count, 2)

    async def test_return_requested_once_until_native_observation(self):
        await self.poll(self.good)
        self.assertEqual(await self.poll(self.locked), 'return_requested')
        self.assertEqual(await self.poll(self.locked), 'return_waiting_for_observation')
        self.assertEqual(self.command.call_count, 2)
        self.assertEqual(await self.poll(self.good), 'checkpoint_recorded')
        self.assertIsNone(self.gate.pending)
        self.assertEqual(self.command.call_count, 3)
        last = self.gate.report()['events'][-1]
        self.assertFalse(last['native_save_written'])
        self.assertTrue(self.gate.report()['experimental'])

    async def test_held_movement_retries_confirmed_return_after_cooldown(self):
        with patch('area_passes.time.monotonic', return_value=100.0) as clock:
            await self.poll(self.good)
            self.assertEqual(await self.poll(self.locked), 'return_requested')
            clock.return_value = 100.9
            self.assertEqual(await self.poll(self.locked), 'return_waiting_for_observation')
            self.assertEqual(self.command.call_count, 2)
            clock.return_value = 101.1
            self.assertEqual(await self.poll(self.locked), 'return_requested')
            self.assertEqual(self.command.call_count, 3)
            clock.return_value = 102.2
            self.assertEqual(await self.poll(self.locked), 'return_requested')
            self.assertEqual(self.command.call_count, 4)

    async def test_passenger_exit_waits_for_foot_then_returns_without_vehicle(self):
        await self.poll(self.good)
        passenger=_snap('SF_Residential_1022',context=157)
        passenger['ride']={'player_role':'passenger'}
        with patch('native_model_transport.area_disembark',side_effect=[
            dict(accepted=True,foot_return_requested=False),dict(accepted=True,foot_return_requested=True)]) as command:
            self.assertEqual(await self.poll(passenger),'disembark_requested')
            self.assertEqual(await self.poll(self.locked),'return_requested')
            self.assertEqual(command.call_count,2)
            self.assertEqual(self.command.call_count,1,'do not teleport the vehicle')
            self.assertEqual(await self.poll(self.good),'checkpoint_recorded')

    async def test_passenger_without_foot_anchor_does_not_force_exit(self):
        with patch('native_model_transport.area_disembark') as command:
            await self.poll(_snap('SF_Docks_0918',context=157))
            self.assertEqual(await self.poll(_snap('SF_Residential_1022',context=11)),
                             'locked_area_without_foot_checkpoint')
            command.assert_not_called()

    async def test_player_driven_tram_also_uses_disembark_path(self):
        await self.poll(self.good)
        tram=_snap('SF_Residential_1022',context=157)
        tram['ride']=dict(player_role='driver',rail_transport=True,model_name='Courser')
        with patch('native_model_transport.area_disembark',return_value=dict(accepted=True,foot_return_requested=False)) as command:
            self.assertEqual(await self.poll(tram),'disembark_requested')
            command.assert_called_once()

    async def test_exit_in_locked_land_switches_vehicle_return_to_foot_anchor(self):
        await self.poll(self.good)
        await self.poll(_snap('SF_Docks_0918',context=157))
        self.gate.pending=dict(state='rejected',code=21,district=FIRST)
        with patch('native_model_transport.area_disembark',return_value=dict(accepted=True,foot_return_requested=True)) as command:
            self.assertEqual(await self.poll(self.locked),'return_requested')
            command.assert_called_once()
            self.assertEqual(self.gate.pending['mode'],'disembark')

    async def test_exit_does_not_clear_uncertain_vehicle_command(self):
        await self.poll(self.good)
        await self.poll(_snap('SF_Docks_0918',context=157))
        self.gate.pending=dict(state='uncertain',district=FIRST)
        with patch('native_model_transport.area_disembark') as command:
            self.assertEqual(await self.poll(self.locked),'return_waiting_for_observation')
            command.assert_not_called()

    async def test_known_refusal_is_not_uncertain_and_never_auto_retried(self):
        await self.poll(self.good)
        self.command.side_effect = RuntimeError(
            'Native command rejected (22): Checkpoint is too distant')
        self.assertEqual(await self.poll(self.locked), 'return_rejected_safe')
        self.assertEqual(await self.poll(self.locked), 'return_rejected_safe')
        self.assertEqual(self.command.call_count, 2)
        self.assertEqual(self.gate.pending['code'], 22)

    async def test_timeout_never_repeats_native_mutation(self):
        await self.poll(self.good)
        self.command.side_effect = RuntimeError('Native command timed out; outcome uncertain')
        self.assertEqual(await self.poll(self.locked), 'return_uncertain')
        self.gate.pending['issued_at'] = -1000
        self.assertEqual(await self.poll(self.locked), 'return_waiting_for_observation')
        self.assertEqual(self.command.call_count, 2)

    async def test_explicit_busy_rejection_can_retry(self):
        from native_model_transport import NativePlayerBusy
        await self.poll(self.good)
        self.command.side_effect = NativePlayerBusy('player unavailable before mutation')
        self.assertEqual(await self.poll(self.locked), 'deferred_player_busy')
        self.assertIsNone(self.gate.pending)
        self.command.side_effect = None
        self.assertEqual(await self.poll(self.locked), 'return_requested')

    async def test_new_seed_binding_never_uses_old_checkpoint(self):
        await self.poll(self.good)
        self.journal = SimpleNamespace(binding_token=b'b' * 16)
        self.assertEqual(await self.poll(self.locked), 'locked_area_without_checkpoint')
        self.assertIsNone(self.gate.checkpoint)
        self.assertEqual(self.command.call_count, 1)

    async def test_unsupported_context_and_standalone_scenes_never_move(self):
        for state in (_snap('SF_Residential_1022', context=27),
                      _snap('SF_Residential_1022', scene='Mine_Tunnel'),
                      _snap('Police_Station_Lobby'),
                      _snap('unknown_1234')):
            with self.subTest(state=state):
                self.assertEqual(await self.poll(state), 'deferred_scene_or_context')
        self.command.assert_not_called()

    async def test_correct_pass_allows_cherry_without_native_return(self):
        self.assertEqual(await self.poll(self.locked, received=[
            dict(category='area_pass', native_name=FIRST)]), 'checkpoint_recorded')
        self.assertEqual(self.gate.checkpoint, FIRST)
        self.assertEqual(self.command.call_count, 1)


if __name__ == '__main__':
    unittest.main()
