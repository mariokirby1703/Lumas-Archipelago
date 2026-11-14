from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from pickup_reader import PickupMemory,attach_source_identities
from client_checks import changed_checks
from monitor_report import event_evidence


class PickupMemoryTests(unittest.TestCase):
    def test_story_superbrick_uses_native_collected_bit_without_city_bit(self):
        source='GAME6/levels/standalones/mine/mine_cavern/mine_cavern.giz:20544:101'
        catalogue={'12':dict(key='source_pickup:'+source,status='static_candidate_unbound',runtime=None)}
        row=dict(source_key=source,native_type=12,native_collected=False)
        snapshot=dict(objectives=dict(records=[]),pickup_bits=[],native_pickups=dict(status='read',objects=[row]))
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[])
        row['native_collected']=True
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[12])
        self.assertEqual(changed_checks(catalogue,None,snapshot,{12})[0],[])
        row['source_key']=None
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[])

    def row(self):
        return dict(collection_bit=1577,name='P_pup1',tile_name='WI_Farmlands_0705',
                    position=[1.,2.,3.],address='0x1234')

    def test_identity_survives_disappearance_and_enriches_pickup(self):
        memory=PickupMemory()
        state=attach_source_identities(dict(status='read',objects=[self.row()]),
              [dict(tile_name='wi_farmlands_0705',name='P_pup1',source_key='source')])
        memory.update(state)
        cached=memory.update(dict(status='read',objects=[]))
        self.assertEqual(cached['objects'][0]['position'],[1.,2.,3.])
        snapshot=dict(pickup_memory=cached,objectives=dict(records=[]),pickup_bits=[1577])
        catalogue={'77':dict(key='source_pickup:source',runtime=None,status='static_candidate_unbound')}
        checks,_=changed_checks(catalogue,dict(objectives=set(),pickups=set()),snapshot)
        self.assertEqual(checks,[77])
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[77])
        result=event_evidence(dict(identity='pickup:1577',text='unknown',kind='superbrick'),{},snapshot)
        self.assertIn('P_pup1',result['text'])
        self.assertEqual(result['evidence']['cached_object_observations'][0]['source_key'],'source')

    def test_conflicts_do_not_send_native_or_dynamic_check(self):
        memory=PickupMemory();memory.update(dict(status='read',objects=[dict(self.row(),source_key='source')]))
        state=memory.update(dict(status='read',objects=[dict(self.row(),name='OTHER',source_key='other')]))
        catalogue={'77':dict(key='source_pickup:source',runtime=dict(kind='pickup',bit=1577),status='native_pickup')}
        snapshot=dict(pickup_memory=state,objectives=dict(records=[]),pickup_bits=[1577])
        self.assertEqual(changed_checks(catalogue,dict(objectives=set(),pickups=set()),snapshot)[0],[])
        self.assertEqual(PickupMemory().bindings,{})

    def test_source_ambiguity_is_not_resolved_by_position(self):
        sources=[dict(tile_name='wi_farmlands_0705',name='P_pup1',source_key=k) for k in ('a','b')]
        state=attach_source_identities(dict(objects=[self.row()]),sources)
        self.assertIsNone(state['objects'][0]['source_key'])
        self.assertEqual(state['objects'][0]['source_candidates'],['a','b'])
