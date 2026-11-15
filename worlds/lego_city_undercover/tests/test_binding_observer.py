from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from client_journal import Journal
from pickup_binding_observer import BindingObserver,binding_overlay,HASH
from pickup_binding_catalogue import detection_catalogue
from client_checks import changed_checks


class BindingObserverTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name);self.journal=Journal(self.root,dict(seed='test',slot=1))
        self.addCleanup(self.journal.close)
        self.source='GAME5/levels/lego_city/lego_city/sf_docks/sf_docks_0012.giz:27:0'
        self.locations={'source_pickup:'+self.source:dict(category='super_bricks',source_type_code=80,source='city.giz')}
        self.observer=BindingObserver(self.locations,{})
        self.snapshot=dict(process=dict(pid=1,sha256=HASH),native_binding=dict(bank='0x12345'),pickup_bits=[],
            native_pickups=dict(status='read',objects=[dict(collection_bit=96,local_index=0,native_type=12,
            source_key=self.source,source_candidates=[self.source],status='native_writer_derived_binding',
            address='0x123456',tile_name='SF_Docks_0012',name='small',position=[1,2,3])]))

    def test_two_observations_survive_reopen_and_tile_unload_without_rebinding_seed(self):
        before=self.journal.binding_token
        self.assertFalse(self.observer.observe(self.snapshot,self.journal))
        self.assertTrue(self.observer.observe(self.snapshot,self.journal))
        unloaded=deepcopy(self.snapshot);unloaded['native_pickups']['objects']=[]
        self.observer.observe(unloaded,self.journal)
        other=Journal(self.root,dict(seed='test',slot=1))
        try:
            bindings,blocked=binding_overlay(other,{})
            self.assertEqual(bindings['96']['source_key'],self.source);self.assertFalse(blocked)
            self.assertEqual(other.binding_token,before)
            active={'1':dict(key='source_pickup:'+self.source,runtime=None)}
            catalog=detection_catalogue(active,bindings)
            state=dict(objectives=dict(records=[]),pickup_bits=[96])
            self.assertEqual(changed_checks(catalog,None,state)[0],[1])
            other.queue([1]);self.assertEqual(other.pending(),[1])
            other.acknowledge([1]);self.assertEqual(changed_checks(catalog,None,state,{1})[0],[])
        finally:other.close()

    def test_no_registration_offset_or_nearest_position_guess(self):
        for mutation in ('ambiguous_name','wrong_type','missing_address','unknown_exe'):
            with self.subTest(mutation=mutation):
                snap=deepcopy(self.snapshot);row=snap['native_pickups']['objects'][0]
                if mutation=='ambiguous_name':row['source_candidates'].append('other.giz:27:0')
                if mutation=='wrong_type':row['native_type']=29
                if mutation=='missing_address':row['address']=None
                if mutation=='unknown_exe':snap['process']['sha256']='unknown'
                self.observer.observe(snap,self.journal);self.observer.observe(snap,self.journal)
                self.assertEqual(self.journal.pickup_bindings(),[])

    def test_runtime_collision_quarantines_packaged_binding(self):
        self.observer.observe(self.snapshot,self.journal);self.observer.observe(self.snapshot,self.journal)
        bad=deepcopy(self.snapshot);bad['native_pickups']['objects'].append(dict(bad['native_pickups']['objects'][0],
            address='0x987654',source_key='other'))
        self.observer.observe(bad,self.journal)
        bindings,blocked=binding_overlay(self.journal,{'96':dict(source_key=self.source)})
        self.assertNotIn('96',bindings);self.assertIn(96,blocked)
        self.observer.observe(self.snapshot,self.journal);self.observer.observe(self.snapshot,self.journal)
        self.assertIn(96,self.journal.pickup_conflicts(),'conflicts must not disappear on tile unload')

    def test_process_or_bank_switch_requires_fresh_registration_pair(self):
        self.observer.observe(self.snapshot,self.journal)
        self.snapshot['native_binding']['bank']='different'
        self.assertFalse(self.observer.observe(self.snapshot,self.journal))
        self.assertEqual(self.journal.pickup_bindings(),[])
        self.assertTrue(self.observer.observe(self.snapshot,self.journal))

    def test_source_at_two_bits_blocks_both_and_collection_transition_is_recorded(self):
        self.observer.observe(self.snapshot,self.journal)
        self.snapshot['pickup_bits']=[96]
        self.observer.observe(self.snapshot,self.journal)
        self.assertTrue(self.journal.pickup_bindings()[0]['collection_transition_observed'])
        row=self.snapshot['native_pickups']['objects'][0];row.update(collection_bit=104,address='0x456789')
        self.observer.observe(self.snapshot,self.journal);self.observer.observe(self.snapshot,self.journal)
        self.assertEqual(self.journal.pickup_conflicts(),{96,104})
