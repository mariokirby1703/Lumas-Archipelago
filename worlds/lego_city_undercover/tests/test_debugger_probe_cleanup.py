from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from pause_debugger_probe import clear_generated_tls_breakpoints

class DebuggerCleanupTests(unittest.TestCase):
    def test_only_generated_single_shot_tls_entries_are_removed(self):
        entries=[SimpleNamespace(name=n,singleshoot=s,addr=i+100) for i,(n,s) in enumerate([
            ('TLS Callback 1 (gdi32full.dll)',True),('PlayerBreakpoint',True),
            ('TLS Callback manual',False)])]
        calls=[]
        client=SimpleNamespace(get_breakpoints=lambda kind:entries,cmd_sync=lambda cmd:calls.append(cmd) or True)
        self.assertEqual(len(clear_generated_tls_breakpoints(client,1)),1)
        self.assertEqual(calls,['bc 0x64'])

    def test_failed_cleanup_is_not_reported_as_success(self):
        client=SimpleNamespace(get_breakpoints=lambda kind:[SimpleNamespace(name='TLS Callback 1',singleshoot=True,addr=100)],cmd_sync=lambda cmd:False)
        with self.assertRaises(RuntimeError):clear_generated_tls_breakpoints(client,1)
