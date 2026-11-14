import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from native_bridge_path import bridge_path

class BridgePathTests(unittest.TestCase):
    def test_legacy_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(bridge_path(tmp),Path(tmp)/'build/lego_city_undercover/LCUItemBridge.dll')
    def test_manifest_selects_parallel_build_and_rejects_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'build/lego_city_undercover';directory.mkdir(parents=True)
            manifest=directory/'native_items_build.json'
            manifest.write_text(json.dumps({'dll_filename':'LCUItemBridgeCategory.dll'}))
            self.assertEqual(bridge_path(tmp),directory/'LCUItemBridgeCategory.dll')
            for value in ('../LCUItemBridge.dll','other.dll',123):
                manifest.write_text(json.dumps({'dll_filename':value}))
                with self.assertRaises(ValueError):bridge_path(tmp)
