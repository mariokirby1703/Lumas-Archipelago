import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import Utils

from ..client.client import MiniGolfContext
from .test_world import generate


class TestClient(unittest.IsolatedAsyncioTestCase):
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
