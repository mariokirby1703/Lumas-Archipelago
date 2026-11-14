import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from item_delivery import effect_plan,register_delivery,entitlement_models
from client_journal import Journal
from client_checks import changed_checks
from model_selection import (model_delivery_ready,ownership_selection_supported,
                             NAVIGATION_PATCHES,LEGACY_SELECTION_RVA,
                             LEGACY_SELECTION_ORIGINAL,LEGACY_SELECTION_PATCHED)


class ItemDeliveryTests(unittest.TestCase):
    def test_owned_only_receipt_needs_booth_compatibility_before_verification(self):
        row=dict(found_bit=False,owned_byte=1)
        self.assertFalse(model_delivery_ready(row,False))
        self.assertTrue(model_delivery_ready(row,True))
        row['owned_byte']=0
        self.assertFalse(model_delivery_ready(row,True))
        row['found_bit']=True
        self.assertFalse(model_delivery_ready(row,True))
        row['owned_byte']=1
        self.assertTrue(model_delivery_ready(row,False))

    def test_booth_support_rejects_unknown_code(self):
        def reader(patched,legacy=LEGACY_SELECTION_ORIGINAL,bad=False):
            mapping={0x100000+rva:(replacement if patched else original) for rva,original,replacement in NAVIGATION_PATCHES}
            mapping[0x100000+LEGACY_SELECTION_RVA]=legacy
            if bad:mapping[0x100000+NAVIGATION_PATCHES[1][0]]=b'\x90'*40
            def read(address,size):
                value=mapping[address];self.assertEqual(size,len(value));return value
            return read
        self.assertFalse(ownership_selection_supported(reader(False),0x100000))
        self.assertTrue(ownership_selection_supported(reader(True),0x100000))
        self.assertFalse(ownership_selection_supported(reader(True,LEGACY_SELECTION_PATCHED),0x100000))
        with self.assertRaises(RuntimeError):ownership_selection_supported(reader(True,bad=True),0x100000)

    def test_ap_ownership_without_discovery_does_not_check_character_token(self):
        catalogue={'1':dict(status='experimental_model_found',runtime=dict(kind='model_found',native_name='COLLECT_2-14_LIFEGUARD'))}
        row=dict(internal_name='Collect_2-14_Lifeguard',group='character',found_bit=False,owned_byte=1,pending_grant=False)
        snapshot=dict(objectives=dict(records=[]),pickup_bits=[],characters=[row])
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[])
        row['found_bit']=True
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[1])
    def test_all_native_cheats_have_exact_item_effects(self):
        world=Path(__file__).resolve().parents[1]
        manifest=json.loads((world/'bridge/cheat_manifest.json').read_text())
        catalogue=json.loads((world/'catalogue.json').read_text())['items']
        cheats=[dict(name=name,**row) for name,row in catalogue.items() if row['category']=='cheat']
        self.assertEqual(len(manifest),40)
        self.assertEqual({r['native_name'] for r in cheats},{r['native_name'] for r in manifest})
        self.assertEqual(len(cheats),40)
        for cheat in cheats:
            self.assertEqual(effect_plan(cheat)['native_name'],cheat['native_name'])
        self.assertEqual(catalogue['Red Brick Cheat: Studs x2']['native_name'],'CHEAT_SCOREX2')

    def test_primary_class_and_character_entitlement_share_native_model(self):
        effects=[dict(name='Ability: Miner',category='ability'),
                 dict(name='Character: MINER',category='character',native_name='MINER')]
        self.assertEqual(entitlement_models(effects),{'MINER'})
        self.assertEqual(effect_plan(dict(effect='add_bricks',amount=10000)),dict(kind='add_bricks',amount=10000))
        with self.assertRaises(ValueError):effect_plan(dict(effect='add_studs',amount=-1))

    def test_receipt_plan_survives_restart_without_false_application(self):
        with tempfile.TemporaryDirectory() as directory:
            binding=dict(seed='delivery-test',slot=1);journal=Journal(Path(directory),binding)
            item=dict(category='character',native_name='MINER')
            with self.assertRaises(ValueError):register_delivery(journal,0,item)
            journal.receipt(0,SimpleNamespace(item=1,location=2,player=1))
            register_delivery(journal,0,item);register_delivery(journal,0,item);journal.close()
            journal=Journal(Path(directory),binding)
            rows=journal.pending_deliveries();self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['state'],'waiting_native_backend')
            with self.assertRaises(ValueError):journal.record_memory_verification(0,dict(found=True,owned=False))
            journal.record_memory_verification(0,dict(found=True,owned=True,save_confirmed=False))
            self.assertEqual(journal.pending_deliveries()[0]['state'],'memory_verified')
            journal.record_memory_verification(0,dict(found=False,owned=True,verified=True,save_confirmed=False))
            self.assertEqual(journal.db.execute('SELECT native_state FROM receipts').fetchone()[0],'not_applied')
            journal.close()
