import asyncio
import sys
from pathlib import Path
from unittest import IsolatedAsyncioTestCase,TestCase
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from test_overrides import TestOverrides,effect_key,supported
from reward_policy import reward_masks

POLICE=dict(name='Ability: Police',category='ability')
COP=dict(name='Character: COP',category='character',native_name='COP')

class TestOverrideTests(TestCase):
    def test_aliases_remove_both_receipt_paths_and_policy_entitlement(self):
        t=TestOverrides();t.set(POLICE,False)
        self.assertTrue(t.blocks(dict(kind='model_unlock',native_name='COP')))
        masks=reward_masks([POLICE,COP],[POLICE,COP],{'COP':227},[],{'ability_items':True,'character_items':True})
        masks=t.policy(masks,{'COP':227},[])
        self.assertIn(227,masks['managed_models']);self.assertNotIn(227,masks['entitled_models'])
        t.set(COP,True);self.assertEqual(len(t.entries),1)
        self.assertIn(227,t.policy(masks,{'COP':227},[])['entitled_models'])
    def test_pending_test_grants_never_turn_into_source_checks(self):
        t=TestOverrides();t.set(POLICE,True)
        snapshot={'characters':[dict(internal_name='COP',pending_grant=True,found_bit=False)]}
        masked=t.mask_snapshot(snapshot)
        self.assertFalse(masked['characters'][0]['pending_grant'])
        self.assertFalse(masked['characters'][0]['found_bit'])
        self.assertTrue(snapshot['characters'][0]['pending_grant'])
    def test_unsupported_and_starting_civilian_removal_are_rejected(self):
        t=TestOverrides()
        with self.assertRaises(ValueError):t.set(dict(name='Story Access: prison',category='story_access'),True)
        with self.assertRaises(ValueError):t.set(dict(name='Civilian',category='character',native_name='CIVILIAN_CHASEMCCAIN'),False)
        self.assertFalse(supported(dict(name='Ability: Climbing',category='ability')))
    def test_reset_marks_entitlements_for_normal_ap_restore_but_does_not_invert_currency(self):
        t=TestOverrides();t.set(POLICE,False)
        t.set(dict(name='Studs 1,000',category='filler',effect='add_studs',amount=1000),True)
        t.reset();self.assertIsNone(t.entries[effect_key(POLICE)][1]);self.assertFalse(t.currency)

class OverrideAsyncTests(IsolatedAsyncioTestCase):
    async def test_uncertain_currency_is_not_automatically_retried(self):
        t=TestOverrides();t.set(dict(name='Studs 1,000',effect='add_studs',amount=1000),True)
        class Session:pid=1
        with patch('native_model_transport.test_currency',side_effect=RuntimeError('timed out')) as command:
            self.assertFalse(await t.apply(Session(),{}, {},[],None))
            self.assertTrue(await t.apply(Session(),{}, {},[],None))
            self.assertEqual(command.call_count,1)
    async def test_ap_owned_reset_returns_control_without_touching_receipts(self):
        t=TestOverrides();t.set(POLICE,False);t.reset()
        class Session:pid=1
        self.assertTrue(await t.apply(Session(),{}, {'COP':227},[COP],None))
        self.assertEqual(t.entries,{})
