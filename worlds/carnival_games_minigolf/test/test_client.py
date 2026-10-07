import asyncio
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
                self.assertIsNone(ctx.runtime.journal.path)
                self.assertFalse(any(Path(directory).iterdir()))
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
    async def test_journal_identity_covers_slot_configuration_and_key_order(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(Utils, 'user_path',
                side_effect=lambda *p: str(Path(directory).joinpath(*p))):
            ctx = MiniGolfContext()
            ctx.send_msgs = AsyncMock()
            ctx.team, ctx.slot = 0, 1
            data = generate().worlds[1].fill_slot_data()
            try:
                ctx.on_package('Connected', {'slot_data': data})
                original = ctx.runtime.journal
                ctx.on_package('Connected', {'slot_data': dict(reversed(list(data.items())))})
                self.assertIs(ctx.runtime.journal, original)
                changed = {**data, 'options': {**data['options'], 'trap_weight': 50}}
                ctx.on_package('Connected', {'slot_data': changed})
                self.assertIsNot(ctx.runtime.journal, original)
                self.assertFalse(any(Path(directory).iterdir()))
            finally:
                ctx.exit_event.set()
                ctx.release_journal()
                await ctx.shutdown()
