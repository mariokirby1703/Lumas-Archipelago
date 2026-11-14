import asyncio
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from client_journal import Journal
from item_delivery import effect_plan
from reward_policy import reward_masks,encode_policy
from test_overrides import TestOverrides,supported

DETECTIVE=dict(name='Ability: Detective Scan',category='ability',classification='progression')
POLICE=dict(name='Ability: Police',category='ability')


class DetectiveGateTests(unittest.IsolatedAsyncioTestCase):
    def test_police_alone_does_not_entitle_detective_scan(self):
        masks=reward_masks([POLICE,DETECTIVE],[POLICE],{'COP':1},[],dict(ability_items=True,detective_scan_lock=True))
        self.assertEqual(masks['managed_runtime'],{0});self.assertEqual(masks['entitled_runtime'],set())
        self.assertEqual(struct.unpack_from('<I',encode_policy(123,bytes(16),masks),12)[0],1)
        masks=reward_masks([DETECTIVE],[DETECTIVE],{},[],dict(ability_items=True,detective_scan_lock=True))
        self.assertEqual(struct.unpack_from('<I',encode_policy(123,bytes(16),masks),12)[0],3)
        self.assertEqual(effect_plan(DETECTIVE),dict(kind='runtime_unlock',ability='DetectiveScan'))

    def test_old_seed_without_new_option_is_not_silently_locked(self):
        masks=reward_masks([DETECTIVE],[],{},[],dict(ability_items=True))
        self.assertFalse(masks['managed_runtime'])

    async def test_gui_override_dispatches_once_and_does_not_claim_native_save(self):
        tester=TestOverrides();self.assertTrue(supported(DETECTIVE))
        tester.set(DETECTIVE,False)
        with patch('native_model_transport.configure_detective_scan',return_value=dict(verified=True)) as configure:
            self.assertTrue(await tester.apply(SimpleNamespace(pid=123),{}, {},[],None))
            self.assertTrue(await tester.apply(SimpleNamespace(pid=123),{}, {},[],None))
            configure.assert_called_once_with(123,False,None)
        self.assertIn(('runtime_unlock','DetectiveScan'),tester.verified)
        self.assertFalse(tester.saved)
        self.assertIn('kein natives Save',tester.history_rows()[0]['save'])
        masks=reward_masks([DETECTIVE],[DETECTIVE],{},[],dict(ability_items=True,detective_scan_lock=True))
        self.assertEqual(tester.policy(masks,{},[])['entitled_runtime'],set())

    def test_runtime_receipt_is_durable_without_fabricated_native_save_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            binding=dict(seed='detective',team=0,slot=2)
            journal=Journal(Path(directory),binding)
            journal.receipt(0,SimpleNamespace(item=123,player=2,location=45))
            journal.plan_delivery(0,effect_plan(DETECTIVE));journal.queue_popup(0,DETECTIVE)
            journal.record_runtime_verification(0,dict(verified=True,native_save_flag=False))
            journal.close();journal=Journal(Path(directory),binding)
            self.assertEqual(journal.reconciliation_deliveries()[0]['state'],'runtime_verified')
            self.assertEqual(journal.next_popup()['index'],0)
            journal.close()
