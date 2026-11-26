import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from assignment_policy import ENTRIES,build_policy,permission
from client_journal import Journal
from goals import ASSIGNMENTS,native_goal_complete


class AssignmentPolicyTests(unittest.TestCase):
    def setUp(self):
        self.binding='12'*16
        self.slot=dict(options=dict(story_access_items=True),item_effects={str(r['item_id']):dict(name=r['item'],category='story_access') for r in ENTRIES})

    def test_all_fifteen_permissions_are_independent(self):
        self.assertEqual(tuple(r['assignment'] for r in ENTRIES),ASSIGNMENTS)
        self.assertEqual(len({r['item_id'] for r in ENTRIES}),15)
        for received in ENTRIES:
            policy=build_policy(self.slot,[dict(item=received['item_id'])]*2,self.binding)
            for target in ASSIGNMENTS:
                self.assertEqual(permission(policy,target,self.binding),target==received['assignment'])
            self.assertFalse(policy['native_gate_installed'])
            self.assertTrue(all(not r['native_acknowledged'] for r in policy['entries']))

    def test_stale_bindings_and_forged_effect_tables_fail_closed(self):
        row=ENTRIES[0]
        policy=build_policy(self.slot,[dict(item=row['item_id'])],self.binding)
        self.assertFalse(permission(policy,row['assignment'],'34'*16))
        self.assertFalse(permission(policy,'blackwells_mansion',self.binding))
        self.slot['item_effects'][str(row['item_id'])]['name']=ENTRIES[1]['item']
        policy=build_policy(self.slot,[dict(item=row['item_id'])],self.binding)
        self.assertFalse(permission(policy,row['assignment'],self.binding))
        for invalid in ('00'*16,'x'*32,'12'*15):
            with self.assertRaises(ValueError):build_policy(self.slot,[],invalid)

    def test_disabled_option_preserves_vanilla_permission_model(self):
        self.slot['options']['story_access_items']=False
        policy=build_policy(self.slot,[],self.binding)
        self.assertTrue(all(permission(policy,name,self.binding) for name in ASSIGNMENTS))
        self.assertFalse(permission(policy,'unknown',self.binding))

    def test_durable_receipts_reconstruct_without_cross_seed_leak(self):
        with TemporaryDirectory() as directory:
            root=Path(directory);binding=dict(seed='a',slot=1)
            journal=Journal(root,binding);item=ENTRIES[9]
            journal.receipt(0,SimpleNamespace(item=item['item_id'],location=1,player=1))
            original=journal.assignment_policy(self.slot);journal.close()
            journal=Journal(root,binding)
            self.assertEqual(journal.assignment_policy(self.slot),original);journal.close()
            journal=Journal(root,dict(seed='b',slot=1))
            fresh=journal.assignment_policy(self.slot)
            self.assertFalse(any(r['received'] for r in fresh['entries']));journal.close()

    def test_registry_ids_are_actual_catalogue_ids(self):
        catalogue=json.loads((Path(__file__).resolve().parents[1]/'catalogue.json').read_text())
        for row in ENTRIES:self.assertEqual(catalogue['items'][row['item']]['id'],row['item_id'])

    def test_goal_accepts_assignment_only_records_without_eager_keyerror(self):
        self.assertTrue(native_goal_complete(dict(level_progress=dict(status='read',records=[dict(assignment='moon_base',complete=True)])),0))
        self.assertFalse(native_goal_complete(dict(level_progress=dict(status='read',records=[dict(complete=True)])),0))
