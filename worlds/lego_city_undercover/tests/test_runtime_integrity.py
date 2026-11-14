import hashlib
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
import file_identity
from hook_ownership import detective_owner,require_current_owner,DETECTIVE_ORIGINAL
from delivery_marker import read_marker,check_snapshot_binding,MARKER_OFFSET


class RuntimeIntegrityTests(unittest.TestCase):
    def test_other_seed_is_rejected_before_checks_or_goal(self):
        token=b'a'*16
        check_snapshot_binding(dict(native_binding=dict(status='unbound',marker=None)),token)
        check_snapshot_binding(dict(native_binding=dict(status='bound',marker=dict(binding=token.hex()))),token)
        with self.assertRaisesRegex(RuntimeError,'checks, goals'):
            check_snapshot_binding(dict(native_binding=dict(status='bound',marker=dict(binding=(b'b'*16).hex()))),token)

    def test_native_binding_reader_rejects_changing_profile(self):
        raw=b'AP'+b'a'*16+struct.pack('<I',2);bank=0x100000
        def read(address,size):
            if address==0x1c7cbb8:return struct.pack('<Q',bank)
            self.assertEqual((address,size),(bank+MARKER_OFFSET,22));return raw
        self.assertEqual(read_marker(read,0)['marker']['next_index'],2)
        calls=0
        def unstable(address,size):
            nonlocal calls
            if address==0x1c7cbb8:
                calls+=1;return struct.pack('<Q',bank if calls==1 else bank+0x1000)
            return raw
        with self.assertRaisesRegex(RuntimeError,'changed'):read_marker(unstable,0)

    def test_hooks_require_the_same_module_path(self):
        self.assertEqual(detective_owner(DETECTIVE_ORIGINAL,[]),{'status':'vanilla'})
        prefix=bytes.fromhex('ff2500000000')+struct.pack('<Q',0x1200)+b'\x90'
        owner=detective_owner(prefix,[dict(base=0x1000,size=0x1000,path=r'C:\build\old.dll')])
        require_current_owner(owner,r'C:\build\old.dll')
        with self.assertRaisesRegex(RuntimeError,'Restart the game'):require_current_owner(owner,r'C:\build\new.dll')
        for observation in (detective_owner(prefix,[]),detective_owner(b'\x90'*15,[])):
            with self.assertRaises(RuntimeError):require_current_owner(observation,r'C:\build\new.dll')

    def test_hash_cache_rechecks_metadata_and_expires(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'game.exe';path.write_bytes(b'first')
            real=hashlib.file_digest
            with patch.object(file_identity.hashlib,'file_digest',wraps=real) as digest:
                first=file_identity.file_digest(path)
                self.assertEqual(first,file_identity.file_digest(path));self.assertEqual(digest.call_count,1)
                file_identity.file_digest(path,ttl=0);self.assertEqual(digest.call_count,2)
                path.write_bytes(b'second')
                self.assertNotEqual(first,file_identity.file_digest(path));self.assertEqual(digest.call_count,3)
