import sys
import struct
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from inventory_reader import parse_mission_token_ids
from client_checks import changed_checks


class TokenCheckTests(unittest.TestCase):
    def test_native_mission_queue(self):
        self.assertEqual(parse_mission_token_ids(struct.pack('<4hB',386,-1,-1,-1,1)),[386])
        for data in (b'',struct.pack('<4hB',386,-1,-1,-1,5),struct.pack('<4hB',-1,-1,-1,-1,1)):
            with self.assertRaises(ValueError):parse_mission_token_ids(data)

    def test_immediate_story_token_and_offline_found_flag(self):
        catalogue={'12':dict(status='experimental_model_found',runtime=dict(kind='model_found',native_name='NPC_CITIZENMALE06'))}
        snapshot=dict(objectives=dict(records=[]),pickup_bits=[],characters=[],
                      mission_tokens=dict(status='read',records=[dict(internal_name='NPC_CitizenMale06')]))
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[12])
        self.assertEqual(changed_checks(catalogue,None,snapshot,{12})[0],[])
        snapshot['mission_tokens']['records']=[]
        snapshot['characters']=[dict(internal_name='NPC_CitizenMale06',group='character',found_bit=True,owned_byte=0)]
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[12])
        snapshot['characters'][0].update(found_bit=False,owned_byte=1)
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[])

    def test_pending_story_disguise_counts_once_before_commit(self):
        catalogue={'23':dict(status='experimental_model_found',runtime=dict(kind='model_found',native_name='MINER'))}
        snapshot=dict(objectives=dict(records=[]),pickup_bits=[],characters=[
            dict(internal_name='Miner',group='character',found_bit=False,owned_byte=0,pending_grant=True),
            dict(internal_name='Buddy_Miner',group='coop_alternative',found_bit=False,pending_grant=True)])
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[23])
        snapshot['characters'][0].update(found_bit=True,pending_grant=False,owned_byte=1)
        self.assertEqual(changed_checks(catalogue,None,snapshot,{23})[0],[])
        snapshot['characters']=snapshot['characters'][1:]
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[])

    def test_unbound_and_ambiguous_tokens_are_not_arbitrary_checks(self):
        catalogue={'12':dict(status='ambiguous_model_source',runtime=None)}
        snapshot=dict(objectives=dict(records=[]),pickup_bits=[],characters=[],
                      mission_tokens=dict(status='read',records=[dict(internal_name='NPC_CitizenMale06')]))
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[])
