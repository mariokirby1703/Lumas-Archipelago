from contextlib import closing
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from gameplay_diagnostics import GameplayDiagnostics
from client_journal import Journal
from area_passes import AreaGate,START,FIRST
from location_reader import read_location

class ObservationTests(unittest.TestCase):
    def test_loading_failure_does_not_reannounce_old_pickups_or_missions(self):
        with tempfile.TemporaryDirectory() as directory, closing(Journal(Path(directory),dict(seed='test',slot=1))) as j:
            tracker=GameplayDiagnostics();snap=dict(process=dict(pid=1),pickup_bits=[1],location=dict(native_tile='SF_Docks_0815',player_position=[1,2,3]),objectives=dict(records=[]))
            tracker.observe(snap,j);tracker.observe(dict(process=dict(pid=1),location=dict(area_status='unresolved'),objectives=dict(status='unresolved')),j)
            tracker.observe(snap,j)
            self.assertEqual(len(j.diagnostics()),1)
            snap['pickup_bits']=[1,2];tracker.observe(snap,j)
            event=j.diagnostics()[0];self.assertEqual(event['kind'],'pickup_bit_transition');self.assertEqual(event['position'],[1,2,3])
            self.assertEqual(j.pending(),[])
    def test_null_city_world_keeps_player_coordinates_without_invalid_reads(self):
        import struct
        pointers={0x1C7D3E0:0x10000,0x10010:0x20000,0x200F0:0x49ECF0,0x1C6A768:0}
        def read(a,n):
            if a==0x101F0:return struct.pack('<4f',1,2,3,1)
            raise AssertionError((a,n))
        with patch('location_reader.pointer',side_effect=lambda r,a:pointers[a]):r=read_location(read,0)
        self.assertEqual(r['player_position'],[1,2,3]);self.assertEqual(r['area_status'],'unresolved')

class AreaPermissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_revoked_checkpoint_is_never_used_as_return_destination(self):
        gate=AreaGate();journal=SimpleNamespace(binding_token=b'x'*16)
        gate.identity=(1,journal.binding_token);gate.checkpoint=FIRST;gate.checkpoint_context=46
        snapshot=dict(location=dict(native_tile='WI_Forest_0803'),actor=dict(status='read',context=dict(index=46)))
        with patch('native_model_transport.area_command') as command:
            result=await gate.poll(SimpleNamespace(pid=1),snapshot,journal,[],'test.dll',True)
        self.assertEqual(result,'locked_area_without_checkpoint');command.assert_not_called()
    async def test_receiving_pass_is_not_evidence_of_a_physical_return(self):
        gate=AreaGate();journal=SimpleNamespace(binding_token=b'x'*16)
        gate.identity=(1,journal.binding_token);gate.checkpoint=START
        gate.pending=dict(state='accepted',district=FIRST,target_position=[0,0,0])
        snapshot=dict(location=dict(native_tile='SF_Residential_0922',player_position=[20,0,0]),actor=dict(status='read',context=dict(index=46)))
        with patch('native_model_transport.area_command',return_value=dict(accepted=True,target_position=[20,0,0])):
            await gate.poll(SimpleNamespace(pid=1),snapshot,journal,[dict(category='area_pass',native_name=FIRST)],'test.dll',True)
        self.assertTrue(gate.last_return_observation['permission_received'])
        self.assertFalse(gate.last_return_observation['returned_from_denied_district'])
