"""Verify client retries without invoking the live game or native bridge."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from pause_menu_client import PauseMenuInstaller
from native_model_transport import NativePlayerBusy


class PauseMenuClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_transient_failure_retries_and_success_is_not_reinstalled(self):
        now=[10]
        configure=Mock(side_effect=[NativePlayerBusy('menu busy'),dict(installed=True,enabled=True)])
        installer=PauseMenuInstaller('bridge.dll',configure=configure,clock=lambda:now[0])
        session=SimpleNamespace(pid=123)
        self.assertIn('warte',await installer.poll(session))
        self.assertIsNone(await installer.poll(session))
        self.assertEqual(configure.call_count,1)
        now[0]+=1
        self.assertIn('Chapter Select aktiv',await installer.poll(session))
        self.assertIsNone(await installer.poll(session))
        self.assertEqual(configure.call_count,2)

    async def test_new_game_process_installs_again_and_negative_ack_is_retried(self):
        now=[10]
        configure=Mock(side_effect=[dict(installed=False,enabled=False),
            dict(installed=True,enabled=True),dict(installed=True,enabled=True)])
        installer=PauseMenuInstaller('bridge.dll',configure=configure,clock=lambda:now[0])
        session=SimpleNamespace(pid=123)
        self.assertIn('warte',await installer.poll(session))
        now[0]+=5
        self.assertIn('aktiv',await installer.poll(session))
        self.assertIn('aktiv',await installer.poll(SimpleNamespace(pid=456)))
        self.assertEqual(configure.call_count,3)
