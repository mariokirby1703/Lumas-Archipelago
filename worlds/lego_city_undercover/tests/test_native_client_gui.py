"""GUI safety/lifecycle tests. Run under xvfb on headless Linux machines."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
try:
    import tkinter as tk
except ImportError:
    tk = None
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'tools/native_client_gui.py'
if tk is not None:
    spec = importlib.util.spec_from_file_location('lcu_gui_tests', MODULE)
    gui = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gui)
else:
    gui = None


@unittest.skipIf(gui is None, 'Tkinter is not installed')
class AddressAndSettingsTests(unittest.TestCase):
    def test_connection_validation(self):
        self.assertEqual(gui.connection_address('archipelago.gg', '58404'), 'archipelago.gg:58404')
        self.assertEqual(gui.connection_address('wss://example.com', 1234), 'wss://example.com:1234')
        self.assertEqual(gui.connection_address('[::1]', '1234'), '[::1]:1234')
        for host, port in (
            ('user:secret@example.com', '1'), ('example.com/path', '2'),
            ('wss://server:1234', 1234), ('host', '70000'),
            ('', 80), ('https://example.com', 80), ('example.com', 'bad'),
            ('[::1', '1234'), ('example.com?token=secret', 80),
        ):
            with self.subTest(host=host, port=port), self.assertRaises(ValueError):
                gui.connection_address(host, port)

    def test_load_settings_whitelists_and_never_loads_password(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps(dict(name='Test', password='secret', native=False,
                                            port='5000', unknown_key='ignored')))
            result = gui.load_settings(path)
            self.assertEqual(result['name'], 'Test')
            self.assertEqual(result['port'], '5000')
            self.assertFalse(result['native'])
            self.assertNotIn('password', result)
            path.write_text('{incomplete json')
            self.assertEqual(gui.load_settings(path)['address'], 'archipelago.gg')

    def test_native_preflight_and_save_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            name = root / 'game1.legocityundercoversavegamedata'
            name.write_bytes(b'test data')
            self.assertEqual(gui.validate_start(False, str(name), root=root, platform='linux'), name)
            with self.assertRaises(ValueError):
                gui.validate_start(True, '', root=root, platform='linux')
            with self.assertRaises(ValueError):
                gui.validate_start(False, str(root / 'missing.legocityundercoversavegamedata'),
                                   root=root, platform='linux')
            with self.assertRaises(ValueError):
                gui.validate_start(False, str(root / 'unexpected.txt'), root=root, platform='linux')


@unittest.skipIf(gui is None, 'Tkinter is not installed')
class WindowTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest('No display for Tk: ' + str(error))
        self.root.withdraw()
        self.settings = tempfile.TemporaryDirectory()
        self.original_settings = gui.SETTINGS
        gui.SETTINGS = Path(self.settings.name) / 'settings.json'
        try:
            self.app = gui.App(self.root, argparse.Namespace(connect=None, name=None,
                                                              native_save_file=None))
        except Exception:
            gui.SETTINGS = self.original_settings
            self.settings.cleanup()
            self.root.destroy()
            raise
        self.root.update_idletasks()

    def tearDown(self):
        gui.SETTINGS = self.original_settings
        self.settings.cleanup()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_search_and_invalid_connect_do_not_start_worker(self):
        self.app.item.set('Police')
        self.root.update_idletasks()
        self.assertGreater(self.app.matches.size(), 0)
        self.assertTrue(all('police' in self.app.matches.get(i).lower()
                            for i in range(self.app.matches.size())))
        self.app.port.set('not-a-number')
        self.app.name.set('Slot')
        self.app.connect()
        self.assertIn('ERROR', self.app.log.get('1.0', 'end'))
        self.assertIsNone(self.app.worker)
        self.assertEqual(self.app.password.get(), '')

    def test_buttons_require_server_game_and_bound_native_save(self):
        class FakeThread:
            def is_alive(self):
                return True
        self.app.worker = FakeThread()
        name = next(n for n in self.app.names if gui.supported(self.app.effects[n]))
        self.app.item.set(name)
        self.app.ap_connected = self.app.game_connected = True
        self.app.update_buttons()
        self.assertTrue(self.app.give_button.instate(['disabled']))
        self.app.native_ready = True
        self.app.update_buttons()
        self.assertFalse(self.app.give_button.instate(['disabled']))
        self.app.events.put(('ready', False))
        # Avoid recursive callbacks by processing a single scheduled pump.
        self.app.pump()
        self.assertTrue(self.app.give_button.instate(['disabled']))
        self.app.worker = None

    def test_status_events_are_rendered_and_stop_resets_controls(self):
        self.app.events.put(('ap', 'Archipelago: Verbunden'))
        self.app.events.put(('connection', True))
        self.app.events.put(('game', 'Spiel: Testmodel'))
        self.app.events.put(('game_loaded', True))
        self.app.events.put(('save', 'Save: game1'))
        self.app.events.put(('progress', 'Checks: 5 · AP-Items: 3'))
        self.app.events.put(('overrides', ['Ability: Police → geben']))
        self.app.pump()
        self.assertEqual(self.app.progress.get(), 'Checks: 5 · AP-Items: 3')
        self.assertEqual(self.app.overrides.size(), 1)
        self.assertTrue(self.app.ap_connected)
        self.app.events.put(('stopped', None))
        self.app.pump()
        self.assertFalse(self.app.ap_connected)
        self.assertFalse(self.app.native_ready)
        self.assertEqual(self.app.game_status.get(), 'Spiel: Nicht geladen')

    def test_window_close_queues_disconnect_and_waits_for_worker(self):
        class FakeThread:
            def is_alive(self):
                return True
        self.app.worker = FakeThread()
        self.app.close()
        self.assertTrue(self.app.closing)
        self.assertTrue(self.app.stopping)
        self.assertEqual(self.app.commands.get_nowait(), ('disconnect', None))
        self.assertFalse(self.app.disconnect_button.instate(['!disabled']))
        self.app.events.put(('stopped', None))
        self.app.pump()
        self.assertIsNone(self.app.worker)

    def test_password_never_written_to_settings_or_event_log(self):
        event_queue = __import__('queue').Queue()
        log = gui.EventLogHandler(event_queue, 'secret-password')
        log.setFormatter(__import__('logging').Formatter('%(message)s'))
        log.emit(__import__('logging').LogRecord('test', 20, __file__, 1,
                     'Connection failed: secret-password', (), None))
        self.assertNotIn('secret-password', event_queue.get_nowait()[1])
        self.app.password.set('secret-password')
        self.app.use_native.set(False)
        self.app.address.set('example.com')
        self.app.port.set('1234')
        self.app.name.set('TestSlot')
        # Don't open a real worker: mock the worker Thread start only.
        with patch.object(gui.threading.Thread, 'start'):
            self.app.connect()
        self.assertTrue(gui.SETTINGS.exists())
        self.assertNotIn('secret-password', gui.SETTINGS.read_text())
        self.app.worker = None
