import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from test_overrides import TestOverrides,effect_key
from test_catalogue import test_catalogue,item_states
from delivery_marker import CHARACTER_SAVE_OFFSET,NATIVE_SAVE_SIZE


def saved_data(model=None,cheat=None):
    data=bytearray(NATIVE_SAVE_SIZE);data[:8]=b'HMGR\x01\0\0\0'
    if model is not None:data[CHARACTER_SAVE_OFFSET+0x80+model]=1
    if cheat is not None:
        offset=CHARACTER_SAVE_OFFSET-0x122e0+0xfa80
        data[offset:offset+8]=(1<<cheat).to_bytes(8,'little')
    return bytes(data)

class SaveProofTests(unittest.IsolatedAsyncioTestCase):
    async def test_skin_grant_and_removal_are_both_verified_from_disk(self):
        class Session:pid=1;base=0;read=None
        for enabled in (True,False):
            t=TestOverrides();effect=dict(name='Ability: Robber',category='ability')
            t.set(effect,enabled);key=effect_key(effect);t.verified.add(key);t.native_ids[key]=228
            with patch('native_save.read_save',return_value=saved_data(model=228 if enabled else None)):
                await t.verify_save(Session(),Path('fake.save'),None)
            self.assertIn(key,t.saved)
            self.assertEqual(t.history_rows()[-1]['save'],'Bestätigt')
    async def test_all_forty_red_brick_ownership_flags_have_disk_proof(self):
        class Session:pid=1;base=0;read=None
        for index in range(40):
            effect=dict(name='Red Brick Cheat: TEST',category='cheat',native_name='TEST')
            t=TestOverrides();t.set(effect,True);key=effect_key(effect);t.verified.add(key);t.native_ids[key]=index
            with patch('native_save.read_save',return_value=saved_data(cheat=index)):
                await t.verify_save(Session(),Path('fake.save'),None)
            self.assertIn(key,t.saved)
    async def test_unconfirmed_disk_flag_requests_one_save_and_does_not_claim_success(self):
        class Session:pid=1;base=0;read=None
        t=TestOverrides();effect=dict(name='Ability: Miner',category='ability');t.set(effect,True)
        key=effect_key(effect);t.verified.add(key);t.native_ids[key]=237
        with patch('native_save.read_save',return_value=saved_data()),patch('save_reader.read_save_controller',return_value=dict(enabled=True,requested=False,state=0)),patch('native_model_transport.request_save') as save:
            await t.verify_save(Session(),Path('fake.save'),None)
            await t.verify_save(Session(),Path('fake.save'),None)
            self.assertEqual(save.call_count,1);self.assertNotIn(key,t.saved)
            self.assertEqual(t.history_rows()[-1]['save'],'Ausstehend')
    def test_history_retains_repeated_operations_separately(self):
        t=TestOverrides();effect=dict(name='Ability: Police',category='ability')
        t.set(effect,True);t.set(effect,False)
        self.assertEqual([r['action'] for r in t.history_rows()],['Geben','Nehmen'])
    def test_roster_includes_uncollected_non_progression_skins(self):
        effects=test_catalogue({'items':{}},{'entries':{'SPECIAL':{'kind':'character','counts_for_progress':False}}})
        self.assertIn('Character: SPECIAL',effects)
        states=item_states(effects,{'characters':[]},{'SPECIAL':400},saved_data())
        self.assertIs(states['Character: SPECIAL']['owned'],False)
        self.assertIs(states['Character: SPECIAL']['saved'],False)
