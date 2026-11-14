"""Regression tests for sparse outfit grants and the pinned native cheat source fix.

No running game or native save is touched.
"""
import asyncio
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

WORLD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD / 'bridge'))
sys.path.insert(0, str(WORLD / 'tools'))
from test_overrides import TestOverrides
import patch_native_cheat_bridge as cheat_patch

ROBBER = dict(name='Ability: Robber', category='ability')
ASTRONAUT = dict(name='Ability: Astronaut', category='ability')
BOOST = dict(name='Red Brick Cheat: CHEAT_BOOST', category='cheat', native_name='CHEAT_BOOST')


class ClassGrantTests(unittest.IsolatedAsyncioTestCase):
    async def test_unfound_robbber_is_not_in_sparse_snapshot_and_can_be_granted(self):
        tester = TestOverrides()
        tester.set(ROBBER, True)
        snapshot = dict(characters=[])
        class Session: pid = 17
        with patch('native_model_transport.grant_model') as grant:
            self.assertFalse(await tester.apply(Session(), snapshot, {'ROBBER': 230}, [], None))
            grant.assert_called_once_with(17, 230, 'ROBBER', None)
            self.assertTrue(await tester.apply(Session(), snapshot, {'ROBBER': 230}, [], None))
            self.assertEqual(grant.call_count, 1, 'Never repeatedly grant on a stale snapshot')
            snapshot['characters'].append(dict(model_id=230, owned_byte=1))
            self.assertTrue(await tester.apply(Session(), snapshot, {'ROBBER': 230}, [], None))
            self.assertIn(('model_unlock', 'ROBBER'), tester.verified)

    async def test_unfound_astronaut_is_granted_and_remove_checks_sparseness(self):
        tester = TestOverrides()
        tester.set(ASTRONAUT, True)
        class Session: pid = 17
        with patch('native_model_transport.grant_model') as grant:
            self.assertFalse(await tester.apply(Session(), dict(characters=[]), {'ASTRONAUT': 245}, [], None))
            grant.assert_called_once_with(17, 245, 'ASTRONAUT', None)
        tester.set(ASTRONAUT, False)
        # Model already absent (not owned): removal should be readback confirmed,
        # not a dangerous blind remove call.
        with patch('native_model_transport.test_remove') as remove:
            self.assertTrue(await tester.apply(Session(), dict(characters=[]), {'ASTRONAUT': 245}, [], None))
            remove.assert_not_called()
            self.assertIn(('model_unlock', 'ASTRONAUT'), tester.verified)

    async def test_unknown_native_model_remains_fail_closed(self):
        tester = TestOverrides()
        tester.set(ROBBER, True)
        class Session: pid = 17
        with patch('native_model_transport.grant_model') as grant:
            self.assertTrue(await tester.apply(Session(), dict(characters=[]), {}, [], None))
            grant.assert_not_called()
            self.assertIn(('model_unlock', 'ROBBER'), tester.errors)

    async def test_cheat_grant_requires_new_readback_not_just_rpc_success(self):
        tester = TestOverrides()
        tester.set(BOOST, True)
        class Session: pid = 17
        state = dict(cheats=dict(status='read', records=[dict(native_name='CHEAT_BOOST', index=37, effect_flag=False)]))
        with patch('native_model_transport.grant_cheat') as grant:
            self.assertFalse(await tester.apply(Session(), state, {}, [], None))
            grant.assert_called_once_with(17, 37, 'CHEAT_BOOST', None)
            self.assertFalse(tester.verified)
            state['cheats']['records'][0]['effect_flag'] = True
            self.assertTrue(await tester.apply(Session(), state, {}, [], None))
            self.assertIn(('cheat_unlock', 'CHEAT_BOOST'), tester.verified)
            self.assertEqual(grant.call_count, 1)


class NativeCheatPatchTests(unittest.TestCase):
    def fixture(self, root):
        path = Path(root) / cheat_patch.SOURCE
        path.parent.mkdir(parents=True, exist_ok=True)
        data = ('// pinned source prelude\n' + cheat_patch.OLD + '// pinned source epilogue\n').encode('utf-8')
        path.write_bytes(data)
        return path, data

    def test_patch_backups_source_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, source = self.fixture(root)
            with patch.object(cheat_patch, 'PINNED_GIT_BLOB', cheat_patch.git_blob_sha(source)):
                self.assertTrue(cheat_patch.apply_patch(root))
                text = path.read_text()
                self.assertIn(cheat_patch.MARKER, text)
                self.assertNotIn('reinterpret_cast<Unlock>(base+0x7f19a0)', text)
                self.assertIn('reinterpret_cast<std::uintptr_t>(effect)!=profile+0xfa80', text)
                self.assertIn('reinterpret_cast<std::uintptr_t>(found)!=profile+0xfa70', text)
                self.assertIn('count!=40', text)
                self.assertIn('*effect|=mask', text)
                self.assertNotIn('*found|=', text)
                self.assertEqual((root / 'build/lego_city_undercover/item_bridge_before_cheat_fix.cpp').read_bytes(), source)
                self.assertFalse(cheat_patch.apply_patch(root))

    def test_changed_cpp_refused_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, source = self.fixture(root)
            with self.assertRaisesRegex(ValueError, 'differs from the reviewed'):
                cheat_patch.apply_patch(root)
            self.assertEqual(path.read_bytes(), source)
            self.assertFalse((root / 'build').exists())

    def test_cpp_statement_compiles_syntactically_if_compiler_available(self):
        compiler = shutil.which('g++') or shutil.which('clang++')
        if not compiler:
            self.skipTest('No host C++ compiler')
        snippet = '''#include <cstdint>
struct Command {unsigned model; unsigned found; unsigned owned;};
unsigned Test(std::uintptr_t base, Command* c) {
    unsigned count=40;
    auto found=reinterpret_cast<std::uint64_t*>(base+0x1c7e848);
    auto effect=reinterpret_cast<std::uint64_t*>(base+0x1c7e850);
    const auto mask=std::uint64_t(1)<<c->model;
''' + cheat_patch.NEW + '''
    c->found=!!(*found&mask);c->owned=!!(*effect&mask);
    return c->owned ? 0 : 7;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'cheat_patch.cpp'
            path.write_text(snippet, encoding='utf-8')
            subprocess.run([compiler, '-std=c++17', '-fsyntax-only', str(path)], check=True, capture_output=True)


if __name__ == '__main__':
    unittest.main()
