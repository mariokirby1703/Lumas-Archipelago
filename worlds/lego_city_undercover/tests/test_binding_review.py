from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from client_journal import Journal
from pickup_binding_observer import BindingObserver,HASH
from pickup_binding_review import review_bindings,validate_proof
from review_journal_bindings import load_journal,register_review


class BindingReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.journal=Journal(self.root,dict(seed='test',slot=1));self.addCleanup(self.journal.close)
        self.source='GAME5/levels/lego_city/lego_city/sf_docks/sf_docks_1200.giz:27:0'
        self.locations={'source_pickup:'+self.source:dict(category='super_bricks',source_type_code=80,
            source=self.source.rsplit(':',2)[0])}
        self.sources=[dict(source_key=self.source,tile_name='sf_docks_1200',name='P_pup',native_type=12)]
        row=dict(source_key=self.source,source_candidates=[self.source],tile_name='SF_Docks_1200',name='P_pup',
            native_type=12,collection_bit=96,local_index=0,tile_xy=[12,0],grid_width=38,
            status='native_writer_derived_binding',address='0x123450',position=[1.,2.,3.],
            type_flags='0x4000000',instance_flags='0x0')
        row['writer_enabled']=True
        snapshot=dict(process=dict(pid=123,sha256=HASH,profile='0x123000'),native_binding=dict(bank='0x200000'),
                      pickup_bits=[],native_pickups=dict(status='read',objects=[row]))
        observer=BindingObserver(self.locations,{})
        observer.observe(snapshot,self.journal);observer.observe(snapshot,self.journal)
        self.proof=self.journal.pickup_bindings()[0]

    def review(self,proofs=None,existing=None,blocked=(),require_collection=False):
        return review_bindings(proofs or [self.proof],existing or {},self.locations,self.sources,blocked,require_collection)

    def test_real_observer_proof_is_reconstructable_and_not_gameplay_verification(self):
        result=self.review()
        self.assertEqual(len(result['accepted']),1);self.assertFalse(result['live_gameplay_verified'])
        self.assertEqual(result['accepted'][0]['status'],'native_writer_two_snapshot_identity')
        self.assertEqual(len(self.review(blocked=[96])['rejected']),1)
        with self.assertRaises(ValueError):self.review(blocked=['96'])

    def test_label_alone_old_proof_or_missing_grid_flags_is_insufficient(self):
        mutations=[dict(proof_version=1),dict(grid_width=None),dict(native_flags={}),dict(observations=[]),dict(writer_enabled=False),
                   dict(game_mutated=True),dict(native_bank='invalid'),dict(instance_address='0x0'),
                   dict(process=dict(pid=123,sha256='unknown')),dict(position=[float('nan'),1,2]),
                   dict(bit=97),dict(native_type=29),dict(native_type=12.0),dict(process=['invalid']),
                   dict(observation_count=2.0),dict(resource='other.giz')]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                proof=dict(self.proof,**mutation)
                self.assertTrue(self.review([proof])['rejected']);self.assertFalse(self.review([proof])['accepted'])

    def test_second_observation_and_native_branch_must_agree(self):
        for mutation in ('address','grid_width','type_flags','status'):
            with self.subTest(field=mutation):
                proof=deepcopy(self.proof);proof['observations'][1][mutation]='different'
                self.assertTrue(self.review([proof])['rejected'])
        proof=deepcopy(self.proof);proof['native_flags']['instance_flags']='0x200'
        self.assertTrue(self.review([proof])['rejected'])

    def test_duplicate_source_name_is_never_resolved_by_position(self):
        other=dict(self.sources[0],source_key='another-source')
        self.sources.append(other)
        self.assertTrue(self.review()['rejected']);self.assertFalse(self.review()['accepted'])

    def test_incoming_and_existing_collisions_reject_instead_of_choose_winner(self):
        existing={'96':dict(source_key='other-source')}
        self.assertTrue(self.review(existing=existing)['rejected'])
        existing={'104':dict(source_key=self.source)}
        self.assertTrue(self.review(existing=existing)['rejected'])
        contradictory=dict(self.proof,bit=104)
        result=self.review([self.proof,contradictory])
        self.assertFalse(result['accepted']);self.assertEqual(len(result['rejected']),2)

    def test_collection_requirement_and_atomic_no_overwrite_registration(self):
        self.assertFalse(self.review(require_collection=True)['accepted'])
        proof=dict(self.proof,collection_transition_observed=True,before_collected=False,after_collected=True)
        review=self.review([proof],require_collection=True)
        target=self.root/'bindings.json';target.write_text('{}')
        original=target.read_bytes()
        self.assertEqual(register_review(target,original,review),1)
        self.assertEqual(json.loads(target.read_text())['96']['source_key'],self.source)
        with self.assertRaises(RuntimeError):register_review(target,original,review)
        result=self.review(existing=json.loads(target.read_text()))
        self.assertFalse(result['accepted']);self.assertEqual(len(result['unchanged']),1)

    def test_read_only_journal_input_and_blocked_bits(self):
        self.journal.pickup_conflict(96,{self.source},'fixture conflict')
        path=next(self.root.glob('*.sqlite3'));before=path.read_bytes()
        proofs,blocked=load_journal(path)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(blocked,{96});self.assertEqual(proofs[0]['source_key'],self.source)

    def test_simultaneous_registration_lock_does_not_replace_catalogue(self):
        target=self.root/'bindings.json';target.write_text('{}')
        lock=target.with_suffix('.json.lock');lock.write_text('other-process')
        with self.assertRaises(FileExistsError):register_review(target,b'{}',self.review())
        self.assertEqual(target.read_bytes(),b'{}')
        self.assertEqual(lock.read_text(),'other-process','must not remove another process lock')

    def test_old_proof_can_refresh_without_losing_collection_evidence(self):
        old=dict(self.proof,proof_version=1,collection_transition_observed=True,before_collected=False,after_collected=True)
        with self.journal.db:
            self.journal.db.execute('UPDATE pickup_bindings SET proof=?',(json.dumps(old),))
        self.assertTrue(self.journal.store_pickup_binding(self.proof))
        upgraded=self.journal.pickup_bindings()[0]
        self.assertEqual(upgraded['proof_version'],2);self.assertTrue(upgraded['collection_transition_observed'])
