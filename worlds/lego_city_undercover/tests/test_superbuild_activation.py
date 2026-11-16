"""SuperBuild must activate its original vanilla job before the receipt autosave.

Synthetic transport tests only. They do NOT verify native Gold Brick, 1/65 or
persistence behaviour in a running LEGO City Undercover process.
"""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from native_delivery import NativeDeliveryEngine


class SuperbuildActivationTests(unittest.IsolatedAsyncioTestCase):
    def setup_case(self, already_unlocked=False):
        events = []
        engine = NativeDeliveryEngine(Path('test.dll'))
        engine.models = {}
        engine.last_save_data = b'synthetic save'
        journal = SimpleNamespace(binding_token=b'x' * 16)
        journal.reconciliation_deliveries = Mock(return_value=[] if already_unlocked else [
            dict(index=9, state='pending', plan=dict(kind='ability_unlock', ability='SuperBuild'))])
        journal.record_memory_verification = Mock(side_effect=lambda *_: events.append('receipt'))
        session = SimpleNamespace(pid=17, base=0x100000, read=lambda *_: bytes(22))
        snapshot = dict(actor=dict(context=dict(index=46)),
                        abilities=dict(SuperBuild=already_unlocked),
                        ability_raw=dict(SuperBuild=dict(existing=int(already_unlocked))),
                        characters=[], cheats=dict(records=[]),
                        story=dict(jobs=dict(SuperBuild_Saves=dict(SuperBuildsActive=False))))
        return events, engine, session, snapshot, journal

    async def test_new_ability_activates_vanilla_jobs_before_receipt_and_save(self):
        events, engine, session, snapshot, journal = self.setup_case()
        def grant(*args):
            events.append('grant')
            return dict(verified=True)
        def enable(*args):
            events.append('enable')
            self.assertEqual(args[1], journal.binding_token)
            return dict(changed=True, enabled=True)
        def save(*args):
            events.append('save')
            return dict(requested=True)
        with patch.object(engine, 'prepare_binding', new_callable=AsyncMock, return_value=True), \
             patch('native_delivery.pointer', return_value=0x400000), \
             patch('native_delivery.reward_masks', return_value={}), \
             patch('native_delivery.encode_policy', return_value=b''), \
             patch('native_delivery.enforce_rewards', return_value=dict(changes=0, switch_requested=False)), \
             patch('native_delivery.tool_class_ready', return_value=True), \
             patch('native_delivery.ownership_selection_supported', return_value=True), \
             patch('native_delivery.grant_ability', side_effect=grant), \
             patch('native_delivery.enable_superbuild_jobs', side_effect=enable), \
             patch('native_delivery.read_save_controller', return_value=dict(enabled=True, requested=False)), \
             patch('native_delivery.request_save', side_effect=save):
            await engine.poll(session, snapshot, journal)
        self.assertEqual(events, ['grant', 'enable', 'receipt', 'save'])
        journal.record_memory_verification.assert_called_once_with(9, dict(verified=True))

    async def test_restart_retries_inactive_job_without_regranting_ability(self):
        events, engine, session, snapshot, journal = self.setup_case(already_unlocked=True)
        def enable(*args):
            events.append('enable')
            return dict(changed=True, enabled=True)
        def save(*args):
            events.append('save')
            return dict(requested=True)
        with patch.object(engine, 'prepare_binding', new_callable=AsyncMock, return_value=True), \
             patch('native_delivery.pointer', return_value=0x400000), \
             patch('native_delivery.reward_masks', return_value={}), \
             patch('native_delivery.encode_policy', return_value=b''), \
             patch('native_delivery.enforce_rewards', return_value=dict(changes=0, switch_requested=False)), \
             patch('native_delivery.enable_superbuild_jobs', side_effect=enable), \
             patch('native_delivery.read_save_controller', return_value=dict(enabled=True, requested=False)), \
             patch('native_delivery.request_save', side_effect=save), \
             patch('native_delivery.grant_ability') as grant:
            await engine.poll(session, snapshot, journal)
            grant.assert_not_called()
        self.assertEqual(events, ['enable', 'save'])

    async def test_busy_autosave_is_retried_after_job_activation(self):
        events, engine, session, snapshot, journal = self.setup_case(already_unlocked=True)
        controller = [dict(enabled=True, requested=True),
                      dict(enabled=True, requested=False)]
        def enable(*_):
            events.append('enable')
            return dict(changed=True, enabled=True)
        def save(*_):
            events.append('save')
            return dict(requested=True)
        with patch.object(engine, 'prepare_binding', new_callable=AsyncMock, return_value=True), \
             patch('native_delivery.pointer', return_value=0x400000), \
             patch('native_delivery.reward_masks', return_value={}), \
             patch('native_delivery.encode_policy', return_value=b''), \
             patch('native_delivery.enforce_rewards', return_value=dict(changes=0, switch_requested=False)), \
             patch('native_delivery.enable_superbuild_jobs', side_effect=enable) as activation, \
             patch('native_delivery.read_save_controller', side_effect=controller), \
             patch('native_delivery.request_save', side_effect=save):
            await engine.poll(session, snapshot, journal)
            self.assertTrue(engine.runtime_states['SuperBuildJobsNeedSave'])
            snapshot['story']['jobs']['SuperBuild_Saves']['SuperBuildsActive'] = True
            await engine.poll(session, snapshot, journal)
            self.assertNotIn('SuperBuildJobsNeedSave', engine.runtime_states)
            activation.assert_called_once()
        self.assertEqual(events, ['enable', 'save'])

    async def test_inactive_job_is_not_falsely_reported_as_confirmed(self):
        events, engine, session, snapshot, journal = self.setup_case()
        def grant(*_):
            events.append('grant')
            return dict(verified=True)
        def enable(*_):
            events.append('enable')
            return dict(changed=False, enabled=False)
        def save(*_):
            events.append('save')
            return dict(requested=True)
        with patch.object(engine, 'prepare_binding', new_callable=AsyncMock, return_value=True), \
             patch('native_delivery.pointer', return_value=0x400000), \
             patch('native_delivery.reward_masks', return_value={}), \
             patch('native_delivery.encode_policy', return_value=b''), \
             patch('native_delivery.enforce_rewards', return_value=dict(changes=0, switch_requested=False)), \
             patch('native_delivery.tool_class_ready', return_value=True), \
             patch('native_delivery.ownership_selection_supported', return_value=True), \
             patch('native_delivery.grant_ability', side_effect=grant), \
             patch('native_delivery.enable_superbuild_jobs', side_effect=enable), \
             patch('native_delivery.read_save_controller', return_value=dict(enabled=True, requested=False)), \
             patch('native_delivery.request_save', side_effect=save):
            with self.assertLogs(level='WARNING') as logs:
                await engine.poll(session, snapshot, journal)
        self.assertEqual(events, ['grant', 'enable', 'receipt', 'save'])
        self.assertTrue(any('not confirmed' in message for message in logs.output))
