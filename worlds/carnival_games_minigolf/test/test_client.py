import asyncio
import io
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
import Utils
from worlds.LauncherComponents import components, icon_paths

from ..client.client import MiniGolfContext, emulation_active
from ..client import launch
from ..components import ICON
from .test_world import generate


class TestClient(unittest.IsolatedAsyncioTestCase):
    def test_launcher_component_uses_packaged_logo(self):
        component = next(component for component in components
                         if component.display_name == 'Carnival Games MiniGolf Client')
        self.assertEqual(component.icon, ICON)
        self.assertEqual(icon_paths[ICON],
                         'ap:worlds.carnival_games_minigolf/assets/MiniGolf Logo.png')

    def test_console_logging_uses_null_handler_without_standard_streams(self):
        logger = logging.Logger('minigolf-frozen-launcher-test')
        with (patch.object(launch.logging, 'getLogger', return_value=logger),
              patch.object(launch.sys, 'stdout', None),
              patch.object(launch.sys, 'stderr', None)):
            launch.init_console_logging()
            logger.info('normal frozen launcher')
        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0], logging.NullHandler)

    def test_console_logging_writes_to_available_stdout(self):
        logger = logging.Logger('minigolf-debug-launcher-test')
        stream = io.StringIO()
        with (patch.object(launch.logging, 'getLogger', return_value=logger),
              patch.object(launch.sys, 'stdout', stream)):
            launch.init_console_logging()
            logger.info('debug launcher output')
        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0], logging.StreamHandler)
        self.assertIn('debug launcher output', stream.getvalue())

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
