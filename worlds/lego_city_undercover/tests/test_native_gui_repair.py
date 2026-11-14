"""Regression tests for local GUI test requests and native DLL version pinning.

No game process or save file is ever opened by these tests.
"""
import asyncio
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

BRIDGE = Path(__file__).resolve().parents[1] / 'bridge'
sys.path.insert(0, str(BRIDGE))
from test_overrides import TestOverrides
from native_build_integrity import bridge_health, source_digest

COP = dict(name='Ability: Police', category='ability')
BOOST = dict(name='Red Brick Cheat: CHEAT_BOOST', category='cheat', native_name='CHEAT_BOOST')


class LocalTestReliability(unittest.IsolatedAsyncioTestCase):
    async def test_model_request_needs_memory_readback_and_is_not_refired(self):
        t = TestOverrides()
        t.set(COP, True)
        snapshot = dict(characters=[dict(model_id=227, owned_byte=0)])
        class Session: pid = 17
        with patch('native_model_transport.grant_model') as grant:
            self.assertFalse(await t.apply(Session(), snapshot, {'COP': 227}, [], None))
            self.assertEqual(grant.call_count, 1)
            self.assertTrue(await t.apply(Session(), snapshot, {'COP': 227}, [], None))
            self.assertEqual(grant.call_count, 1)
            self.assertFalse(t.verified)
            snapshot['characters'][0]['owned_byte'] = 1
            self.assertTrue(await t.apply(Session(), snapshot, {'COP': 227}, [], None))
            self.assertIn(('model_unlock', 'COP'), t.verified)
            self.assertIn('bestätigt', t.status_rows()[0].lower())

    async def test_uncertain_remove_is_not_retried_even_through_policy(self):
        t = TestOverrides()
        t.set(COP, False)
        snapshot = dict(characters=[dict(model_id=227, owned_byte=1)])
        class Session: pid = 17
        with patch('native_model_transport.test_remove', side_effect=RuntimeError('Native command 18 timed out')) as remove:
            self.assertFalse(await t.apply(Session(), snapshot, {'COP': 227}, [], None))
            self.assertTrue(await t.apply(Session(), snapshot, {'COP': 227}, [], None))
            self.assertEqual(remove.call_count, 1)
        masks = dict(managed_models=set(), entitled_models=set(), managed_abilities=set(),
                     entitled_abilities=set(), managed_cheats=set(), entitled_cheats=set())
        self.assertNotIn(227, t.policy(masks, {'COP': 227}, [])['managed_models'])
        self.assertIn('Unklar', t.status_rows()[0])
        # A fresh manual click, not a polling loop, authorizes another try.
        t.set(COP, False)
        self.assertFalse(t.errors)
        with patch('native_model_transport.test_remove') as remove:
            self.assertFalse(await t.apply(Session(), snapshot, {'COP': 227}, [], None))
            self.assertEqual(remove.call_count, 1)

    async def test_cheat_grant_is_only_confirmed_after_effect_readback(self):
        t = TestOverrides()
        t.set(BOOST, True)
        class Session: pid = 17
        data = dict(cheats=dict(records=[dict(native_name='CHEAT_BOOST', index=37, effect_flag=False)]))
        with patch('native_model_transport.grant_cheat') as grant:
            self.assertFalse(await t.apply(Session(), data, {}, [], None))
            self.assertEqual(grant.call_count, 1)
            self.assertFalse(t.verified)
            data['cheats']['records'][0]['effect_flag'] = True
            self.assertTrue(await t.apply(Session(), data, {}, [], None))
            self.assertTrue(t.verified)
            self.assertEqual(grant.call_count, 1)

    async def test_busy_is_safe_defer_and_can_retry_later(self):
        from native_model_transport import NativePlayerBusy
        t = TestOverrides()
        t.set(COP, True)
        class Session: pid = 17
        snapshot = dict(characters=[dict(model_id=227, owned_byte=0)])
        with patch('native_model_transport.grant_model', side_effect=[NativePlayerBusy('busy'), None]) as grant:
            self.assertFalse(await t.apply(Session(), snapshot, {'COP': 227}, [], None))
            self.assertFalse(t.attempted)
            self.assertFalse(await t.apply(Session(), snapshot, {'COP': 227}, [], None))
            self.assertEqual(grant.call_count, 2)


class BuildHealthTests(unittest.TestCase):
    def test_missing_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertIsNotNone(bridge_health(Path(temp)))

    def test_source_digest_stable_and_sensitive_to_native_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = ['worlds/lego_city_undercover/bridge/native/item_bridge.cpp',
                     'worlds/lego_city_undercover/bridge/native/test_items.h',
                     'worlds/lego_city_undercover/bridge/purchase_gate.py',
                     'worlds/lego_city_undercover/bridge/model_selection.py',
                     'worlds/lego_city_undercover/bridge/category_selection.py',
                     'worlds/lego_city_undercover/bridge/native_context_policy.py',
                     'worlds/lego_city_undercover/tools/build_item_bridge.py']
            for path in paths:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('version 1', encoding='utf-8')
            old = source_digest(root)
            self.assertEqual(source_digest(root), old)
            (root / paths[1]).write_text('version 2', encoding='utf-8')
            self.assertNotEqual(source_digest(root), old)


if __name__ == '__main__':
    unittest.main()
