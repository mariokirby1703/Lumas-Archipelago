import asyncio
import json
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import closing
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from client_journal import Journal
from gameplay_diagnostics import GameplayDiagnostics
from native_delivery import NativeDeliveryEngine
from delivery_marker import NATIVE_SAVE_SIZE,CHARACTER_SAVE_OFFSET,MARKER_OFFSET


class ReliabilityIntegrityTests(unittest.IsolatedAsyncioTestCase):
    async def test_foreign_disk_binding_stops_before_any_grant_or_backup_rewrite(self):
        with tempfile.TemporaryDirectory() as directory, closing(Journal(Path(directory),dict(seed='ours',slot=1))) as journal:
            engine=NativeDeliveryEngine('test.dll');engine.path=Path('already_bound.save')
            engine.identity=(1,journal.binding_token,123)
            data=bytearray(NATIVE_SAVE_SIZE);data[:8]=b'HMGR\x01\0\0\0'
            offset=CHARACTER_SAVE_OFFSET+MARKER_OFFSET
            data[offset:offset+22]=b'AP'+b'foreign-binding!'+struct.pack('<I',0)
            session=SimpleNamespace(pid=1,base=0,read=lambda a,n:struct.pack('<Q',123))
            snapshot=dict(actor=dict(context=dict(index=46)))
            with patch('native_delivery.read_save',return_value=bytes(data)),patch('native_delivery.grant_model') as grant,\
                 patch('native_delivery.ensure_backup') as backup:
                await engine.poll(session,snapshot,journal)
                self.assertFalse(engine.binding_ready);self.assertIn('another AP',engine.last_problem)
                grant.assert_not_called();backup.assert_not_called()

    async def test_profile_switch_clears_path_in_passenger_context_before_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory, closing(Journal(Path(directory),dict(seed='ours',slot=1))) as journal:
            engine=NativeDeliveryEngine('test.dll');engine.path=Path('old_slot.save')
            engine.identity=(1,journal.binding_token,111)
            session=SimpleNamespace(pid=1,base=0,read=lambda a,n:struct.pack('<Q',222))
            with patch('native_delivery.resolve_save',side_effect=RuntimeError('save not stable')),\
                 patch('native_delivery.request_save') as save:
                result=await engine.prepare_binding(session,dict(actor=dict(context=dict(index=11))),journal)
                self.assertFalse(result);self.assertIsNone(engine.path);self.assertFalse(engine.binding_ready)
                save.assert_not_called()

    async def test_diagnostics_are_bounded_change_only_and_not_mutations(self):
        with tempfile.TemporaryDirectory() as directory, closing(Journal(Path(directory),dict(seed='ours',slot=1))) as journal:
            tracker=GameplayDiagnostics()
            snap=dict(process=dict(pid=1),native_binding=dict(bank='x'),pickup_bits=[],
                      location=dict(native_tile='SF_Docks_0012'),objectives=dict(records=[]))
            tracker.observe(snap,journal);first=journal.diagnostic_revision()
            tracker.observe(snap,journal);self.assertEqual(journal.diagnostic_revision(),first)
            snap['pickup_bits']=[96];tracker.observe(snap,journal)
            self.assertEqual(journal.diagnostics()[0]['kind'],'pickup_bit_transition')
            self.assertFalse(journal.diagnostics()[0]['mutation'])
            self.assertEqual(journal.pending(),[],'diagnostics are not AP checks')
            for index in range(1001):journal.diagnostic(dict(kind='fixture',index=index,mutation=False))
            self.assertEqual(len(journal.diagnostics(10000)),1000)
