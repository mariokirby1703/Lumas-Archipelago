from pathlib import Path
import sys
import tempfile
import unittest
WORLD=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORLD/'tools'));sys.path.insert(0,str(WORLD/'bridge'))
from archive_index import safe_target
from client_checks import changed_checks
from client_journal import Journal
from types import SimpleNamespace


class ReviewRegressionTests(unittest.TestCase):
    def test_checks_survive_restart_until_server_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            binding=dict(seed='test',team=0,slot=1)
            journal=Journal(Path(directory),binding)
            journal.queue([123,123,456]);journal.close()
            journal=Journal(Path(directory),binding)
            self.assertEqual(journal.pending(),[123,456])
            journal.acknowledge([123]);self.assertEqual(journal.pending(),[456])
            item=SimpleNamespace(item=10,location=20,player=1)
            journal.receipt(0,item);journal.receipt(0,item)
            self.assertEqual(journal.db.execute('SELECT native_state FROM receipts').fetchone()[0],'not_applied')
            with self.assertRaises(ValueError):
                journal.receipt(0,SimpleNamespace(item=11,location=20,player=1))
            journal.close()
            other=Journal(Path(directory),dict(seed='other',team=0,slot=1))
            self.assertEqual(other.pending(),[]);other.close()

    def test_known_collision_blocked_without_runtime_observation(self):
        catalogue={'1':dict(status='native_pickup',runtime=dict(kind='pickup',bit=5848)),
                   '2':dict(status='native_pickup',runtime=dict(kind='pickup',bit=1577))}
        snapshot=dict(objectives=dict(records=[]),pickup_bits=[5848,1577])
        checks,_=changed_checks(catalogue,dict(objectives=set(),pickups={5848}),snapshot)
        self.assertEqual(checks,[2])
        self.assertEqual(changed_checks(catalogue,dict(objectives=set(),pickups=set()),
            dict(objectives=dict(records=[]),pickup_bits=[5848]))[0],[])

    def test_late_loaded_completed_objective_is_reconciled(self):
        from research_profile import symbol_hash
        name='test';key=symbol_hash(name)
        catalogue={'1':dict(status='native_objective',runtime=dict(kind='objective',name=name))}
        def sample(records):return dict(objectives=dict(records=records),pickup_bits=[])
        _,baseline=changed_checks(catalogue,None,sample([]))
        complete=dict(name_hash=key,candidate_complete=True)
        self.assertEqual(changed_checks(catalogue,baseline,sample([complete]))[0],[1])
        _,baseline=changed_checks(catalogue,None,sample([dict(name_hash=key,candidate_complete=False)]))
        self.assertEqual(changed_checks(catalogue,baseline,sample([complete]))[0],[1])

    def test_existing_save_and_bulk_progress_are_reconciled(self):
        catalogue={'1':dict(status='native_pickup',runtime=dict(kind='pickup',bit=1))}
        def sample(bits):return dict(objectives=dict(records=[]),pickup_bits=bits)
        self.assertEqual(changed_checks(catalogue,None,sample([1]))[0],[1])
        self.assertEqual(changed_checks(catalogue,None,sample([1]),{1})[0],[])
        _,baseline=changed_checks(catalogue,None,sample([]))
        self.assertEqual(changed_checks(catalogue,baseline,sample([1,2,3]))[0],[1])
        _,baseline=changed_checks(catalogue,None,sample([2]))
        self.assertEqual(changed_checks(catalogue,baseline,sample([1]))[0],[1])

    def test_windows_rooted_and_other_archive_escapes(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ('',r'\file.txt',r'\\server\share\file',r'C:relative',r'C:\file',
                         '../file','folder/file:stream'):
                with self.subTest(name=name),self.assertRaises(ValueError):
                    safe_target(Path(directory),name)
            self.assertEqual(safe_target(Path(directory),'folder/file.txt'),Path(directory)/'folder'/'file.txt')

    def test_offline_pickup_reconciles_when_identity_becomes_available(self):
        catalogue={'7':dict(key='source_pickup:test',status='static_candidate_unbound')}
        snapshot=dict(objectives=dict(records=[]),pickup_bits=[1577])
        _,previous=changed_checks(catalogue,None,snapshot)
        snapshot['pickup_memory']=dict(objects=[dict(source_key='test',collection_bit=1577)])
        self.assertEqual(changed_checks(catalogue,previous,snapshot)[0],[7])
        self.assertEqual(changed_checks(catalogue,None,snapshot,{7})[0],[])

    def test_incomplete_snapshot_resets_detection_baseline(self):
        before=dict(objectives={1},pickups={2})
        self.assertEqual(changed_checks({},before,dict(objectives=dict(status='not_initialized'))),([],None))
        snapshot=dict(objectives=dict(status='read',records=[]),pickup_bits=[99])
        checks,baseline=changed_checks({},None,snapshot)
        self.assertEqual(checks,[]);self.assertEqual(baseline['pickups'],{99})
