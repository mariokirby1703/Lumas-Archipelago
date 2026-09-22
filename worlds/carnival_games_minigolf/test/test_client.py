import asyncio
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import Utils

from ..client.client import MiniGolfContext, emulation_active
from .test_world import generate


class TestClient(unittest.IsolatedAsyncioTestCase):
    def test_process_hook_without_active_emulation_is_rejected(self):
        class Status:
            def __init__(self, name):
                self.name = name

        dolphin = type('Dolphin', (), {'is_hooked': staticmethod(lambda: True),
                                       'get_status': staticmethod(lambda: Status('noEmu'))})
        self.assertFalse(emulation_active(dolphin))
        dolphin.get_status = staticmethod(lambda: Status('hooked'))
        self.assertTrue(emulation_active(dolphin))

    async def test_empty_history_barrier_and_disconnect(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(Utils, 'user_path',
                side_effect=lambda *p: str(Path(directory).joinpath(*p))):
            ctx = MiniGolfContext()
            ctx.send_msgs = AsyncMock()
            ctx.team, ctx.slot = 0, 1
            try:
                ctx.on_package('Connected', {'slot_data': generate().worlds[1].fill_slot_data()})
                self.assertIsNotNone(ctx.runtime)
                self.assertFalse(ctx.history_ready)
                await asyncio.sleep(0)
                ctx.send_msgs.assert_awaited_with([{'cmd': 'Get', 'keys': ['_cgm_history_barrier']}])
                ctx.on_package('Retrieved', {'keys': {'_cgm_history_barrier': None}})
                self.assertTrue(ctx.history_ready)
                ctx.reset_server_state()
                self.assertFalse(ctx.history_ready)
                self.assertIsNone(ctx.runtime)
                self.assertIsNone(ctx.journal_lock)
            finally:
                ctx.exit_event.set()
                ctx.release_journal()
                await ctx.shutdown()

    async def test_second_client_cannot_open_same_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = MiniGolfContext(), MiniGolfContext()
            try:
                path = Path(directory) / 'same.json'
                first.acquire_journal(path)
                with self.assertRaisesRegex(ValueError, 'Another MiniGolf client'):
                    second.acquire_journal(path)
                first.release_journal()
                second.acquire_journal(path)
            finally:
                for ctx in (first, second):
                    ctx.exit_event.set()
                    ctx.release_journal()
                    await ctx.shutdown()

    async def test_journal_identity_covers_slot_configuration_and_key_order(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(Utils, 'user_path',
                side_effect=lambda *p: str(Path(directory).joinpath(*p))):
            ctx = MiniGolfContext()
            ctx.send_msgs = AsyncMock()
            ctx.team, ctx.slot = 0, 1
            data = generate().worlds[1].fill_slot_data()
            try:
                ctx.on_package('Connected', {'slot_data': data})
                original = ctx.runtime.journal.path
                ctx.on_package('Connected', {'slot_data': dict(reversed(list(data.items())))})
                self.assertEqual(ctx.runtime.journal.path, original)
                changed = {**data, 'options': {**data['options'], 'trap_weight': 50}}
                ctx.on_package('Connected', {'slot_data': changed})
                self.assertNotEqual(ctx.runtime.journal.path, original)
            finally:
                ctx.exit_event.set()
                ctx.release_journal()
                await ctx.shutdown()

    async def test_legacy_journal_is_not_silently_replayed(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(Utils, 'user_path',
                side_effect=lambda *p: str(Path(directory).joinpath(*p))):
            ctx = MiniGolfContext()
            ctx.team, ctx.slot = 0, 1
            data = generate().worlds[1].fill_slot_data()
            identity = json.dumps([data['schema_version'], data['seed_name'], 0, 1, 0])
            key = hashlib.sha256(identity.encode()).hexdigest()
            path = Path(directory) / 'carnival_games_minigolf' / (key + '.json')
            path.parent.mkdir()
            path.write_text('{}')
            try:
                ctx.on_package('Connected', {'slot_data': data})
                self.assertIsNone(ctx.runtime)
                self.assertIn('legacy receipt journal', ctx.runtime_error)
            finally:
                ctx.exit_event.set()
                ctx.release_journal()
                await ctx.shutdown()
