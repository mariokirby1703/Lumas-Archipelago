import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

p=Path(__file__).resolve().parents[1]/'tools/native_client_gui.py'
spec=importlib.util.spec_from_file_location('lcu_workflow_gui',p);gui=importlib.util.module_from_spec(spec);spec.loader.exec_module(gui)

class UiWorkflowTests(unittest.TestCase):
    def setUp(self):
        try:self.root=tk.Tk();self.root.withdraw()
        except tk.TclError as error:self.skipTest(str(error))
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        root=Path(self.directory.name)
        self.patch=patch.object(gui,'ROOT',root);self.patch.start();self.addCleanup(self.patch.stop)
        self.settings=patch.object(gui,'SETTINGS',root/'settings.json');self.settings.start();self.addCleanup(self.settings.stop)
        self.app=gui.App(self.root,argparse.Namespace(connect=None,name=None,native_save_file=None))
        self.addCleanup(self.root.destroy)
    def test_selecting_item_preserves_search_results(self):
        self.app.item.set('Police');self.root.update_idletasks();size=self.app.matches.size()
        self.assertGreater(size,1)
        self.app.matches.selection_set(0);self.app.select_item(None)
        self.assertEqual(self.app.matches.size(),size)
        self.assertIn(self.app.item.get(),self.app.effects)
    def test_history_updates_in_place_and_survives_next_connection(self):
        row=dict(id=1,time='12:00',action='Geben',item='Ability: Police',ram='Bestatigt',save='Ausstehend',detail='')
        self.app.update_history([row]);self.app.update_history([dict(row,save='Bestatigt')])
        self.assertEqual(len(self.app.history_view.get_children()),1)
        self.app.history_session='next';self.app.update_history([])
        self.assertEqual(len(self.app.history_view.get_children()),1)
        saved=json.loads(self.app.history_path.read_text(encoding='utf-8'))
        self.assertEqual(saved[0]['save'],'Bestatigt')
