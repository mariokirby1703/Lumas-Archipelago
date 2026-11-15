from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from record_pickup_bindings import derive_bindings,HASH
from pickup_binding_catalogue import detection_catalogue
from client_checks import changed_checks
from delivery_marker import binding_token


class NewBindingTests(unittest.TestCase):
    def fixture(self):
        row=dict(collection_bit=100,source_key='city.giz:20:0',native_type=12,
            status='native_writer_derived_binding',name='small',position=[1,2,3],local_index=0,tile_xy=[1,2],writer_enabled=True)
        snap=dict(process=dict(pid=123,sha256=HASH),native_binding=dict(status='bound',marker=dict(binding='abc')),
                  native_pickups=dict(status='read',objects=[row]))
        catalogue=dict(locations={'source_pickup:city.giz:20:0':dict(category='super_bricks',native_type='Gold Plate',source='city.giz')})
        return [snap,deepcopy(snap)],catalogue

    def test_unique_stable_typed_binding_and_no_proximity_fallback(self):
        snapshots,catalogue=self.fixture();rows,conflicts=derive_bindings(snapshots,{},catalogue)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['source_type'],80);self.assertFalse(conflicts)
        snapshots[1]['native_pickups']['objects'][0]['source_key']=None
        self.assertEqual(derive_bindings(snapshots,{},catalogue)[0],[])

    def test_conflicts_type_and_identity_mismatch_are_not_promoted(self):
        snapshots,catalogue=self.fixture()
        self.assertFalse(derive_bindings(snapshots,{'100':dict(source_key='another')},catalogue)[0])
        snapshots[0]['native_pickups']['objects'][0]['native_type']=29
        snapshots[1]['native_pickups']['objects'][0]['native_type']=29
        self.assertFalse(derive_bindings(snapshots,{},catalogue)[0])
        snapshots[1]['process']['sha256']='unknown'
        with self.assertRaisesRegex(ValueError,'identity'):derive_bindings(snapshots,{},catalogue)

    def test_old_seed_detection_gains_binding_without_rebinding_its_journal(self):
        original={'1':dict(key='source_pickup:city.giz:20:0',status='static_candidate_unbound',runtime=None)}
        before=deepcopy(original);token=binding_token(dict(catalogue=original,seed='old'))
        detected=detection_catalogue(original,{'100':dict(source_key='city.giz:20:0')})
        snapshot=dict(objectives=dict(records=[]),pickup_bits=[100])
        self.assertEqual(changed_checks(detected,None,snapshot)[0],[1])
        self.assertEqual(changed_checks(detected,None,snapshot,{1})[0],[])
        self.assertEqual(original,before);self.assertEqual(binding_token(dict(catalogue=original,seed='old')),token)
