import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from area_passes import AreaGate,allowed_districts,tile_district


class AreaIdentityTests(unittest.TestCase):
    def test_always_auburn_and_exact_tile_prefix(self):
        self.assertEqual(allowed_districts([]),{'SF_Docks'})
        for tile,expected in [('SF_Docks_0918','SF_Docks'),('NY_Downtown_East_1718','NY_Downtown_East'),
                              ('NY_Monaco_Tunnel_1920','NY_Tunnel'),('Police_Station_Lobby',None),('plantpot_1234',None)]:
            self.assertEqual(tile_district(tile),expected)
        self.assertEqual(allowed_districts([dict(category='area_pass',name='Area Pass: sf_residential')]),{'SF_Docks','SF_Residential'})
        from native_context_policy import allows_native_command
        self.assertTrue(allows_native_command(157,22))
        self.assertTrue(allows_native_command(11,22))
        for context in (27,2):self.assertFalse(allows_native_command(context,22))
        self.assertFalse(allows_native_command(46,22,False))


class AreaControllerTests(unittest.IsolatedAsyncioTestCase):
    async def test_capture_return_verify_without_repeating_uncertain_mutation(self):
        gate=AreaGate();session=SimpleNamespace(pid=1);journal=SimpleNamespace(binding_token=b'a'*16)
        def snapshot(tile,context=46):return dict(actor=dict(status='read',context=dict(index=context)),location=dict(native_tile=tile))
        good=snapshot('SF_Docks_0918');bad=snapshot('SF_Residential_1022')
        with patch('native_model_transport.area_command',return_value=dict(accepted=True)) as command:
            self.assertEqual(await gate.poll(session,good,journal,[],'bridge.dll'),'waiting_for_save_backup')
            self.assertEqual(await gate.poll(session,good,journal,[],'bridge.dll',True),'checkpoint_recorded')
            self.assertEqual(await gate.poll(session,bad,journal,[],'bridge.dll',True),'return_requested')
            self.assertEqual(await gate.poll(session,bad,journal,[],'bridge.dll',True),'return_waiting_for_observation')
            self.assertEqual(command.call_count,2)
            await gate.poll(session,good,journal,[],'bridge.dll',True)
            self.assertIsNone(gate.pending)
        gate=AreaGate();gate.identity=(1,b'a'*16);gate.checkpoint='SF_Docks'
        with patch('native_model_transport.area_command',side_effect=RuntimeError('timeout')) as command:
            self.assertEqual(await gate.poll(session,bad,journal,[],'bridge.dll',True),'return_uncertain')
            self.assertEqual(await gate.poll(session,bad,journal,[],'bridge.dll',True),'return_waiting_for_observation')
            command.assert_called_once()

    async def test_cutscene_unknown_area_and_missing_anchor_never_teleport(self):
        gate=AreaGate();session=SimpleNamespace(pid=1);journal=SimpleNamespace(binding_token=b'a'*16)
        for tile,context,expected in [('SF_Residential_1022',27,'deferred_scene_or_context'),
            ('Police_Station_Lobby',46,'deferred_scene_or_context'),('SF_Residential_1022',46,'locked_area_without_checkpoint')]:
            with patch('native_model_transport.area_command') as command:
                state=dict(actor=dict(status='read',context=dict(index=context)),location=dict(native_tile=tile))
                self.assertEqual(await gate.poll(session,state,journal,[],'bridge.dll',True),expected);command.assert_not_called()
