import argparse
import importlib.util
from pathlib import Path
import tkinter as tk
from unittest import TestCase

p=Path(__file__).resolve().parents[1]/'tools/native_client_gui.py'
spec=importlib.util.spec_from_file_location('lcu_gui_tests',p);gui=importlib.util.module_from_spec(spec);spec.loader.exec_module(gui)

class GuiTests(TestCase):
    def test_addresses_validate_port_and_reject_embedded_credentials(self):
        self.assertEqual(gui.connection_address('archipelago.gg','58404'),'archipelago.gg:58404')
        self.assertEqual(gui.connection_address('wss://example.com','1234'),'wss://example.com:1234')
        self.assertEqual(gui.connection_address('[::1]','1234'),'[::1]:1234')
        for host,port in (('user:secret@example.com','1'),('example.com/path','2'),('host','70000')):
            with self.assertRaises(ValueError):gui.connection_address(host,port)
    def test_window_builds_search_filters_and_invalid_connect_shows_error(self):
        root=tk.Tk();root.withdraw()
        try:
            app=gui.App(root,argparse.Namespace(connect=None,name=None,native_save_file=None));root.update_idletasks()
            app.item.set('Police');root.update_idletasks()
            self.assertGreater(app.matches.size(),0)
            self.assertTrue(all('police' in app.matches.get(i).lower() for i in range(app.matches.size())))
            app.port.set('bad');app.connect()
            self.assertIn('ERROR',app.log.get('1.0','end'))
            self.assertIsNone(app.thread)
            self.assertEqual(app.password.get(),'')
        finally:root.destroy()
