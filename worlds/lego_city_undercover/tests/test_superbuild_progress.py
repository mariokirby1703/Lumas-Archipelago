import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from superbuild_progress import BINDINGS,reconcile_superbuild_objectives
from research_profile import symbol_hash
from client_checks import changed_checks
from research_superbuild_jobs import pairs

class PersistentSuperbuildTests(unittest.TestCase):
    def test_all_65_keep_original_ids_and_unique_persistent_identity(self):
        catalogue=json.loads((Path(__file__).resolve().parents[1]/'catalogue.json').read_text())['locations']
        self.assertEqual({r['native_id'] for r in BINDINGS},set(range(1,66)))
        self.assertEqual(len({r['job'] for r in BINDINGS}),65)
        for r in BINDINGS:self.assertEqual(catalogue['objective:'+r['objective']]['id'],r['ap_id'])
    def test_unloaded_completed_build_reconciles_and_does_not_repeat(self):
        for r in BINDINGS:
            snapshot=dict(objectives=dict(status='read',records=[]),pickup_bits=[],story=dict(status='read',jobs={
                r['job']:dict(nState=2,nID=r['native_id'])}))
            catalogue={str(r['ap_id']):dict(key='objective:'+r['objective'],status='native_objective',runtime=dict(kind='objective',name=r['objective']))}
            self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[r['ap_id']])
            self.assertEqual(changed_checks(catalogue,None,snapshot,{r['ap_id']})[0],[])
    def test_discovery_or_wrong_id_never_fabricates_a_completed_build(self):
        r=BINDINGS[0];h=symbol_hash(r['objective'])
        self.assertEqual(reconcile_superbuild_objectives({h},dict(status='read',jobs={r['job']:dict(nState=1,nID=r['native_id'])})),set())
        self.assertEqual(reconcile_superbuild_objectives(set(),dict(status='read',jobs={r['job']:dict(nState=2,nID=999)})),set())
        self.assertEqual(reconcile_superbuild_objectives({h},dict(status='unresolved',jobs={})),{h})
    def test_parser_requires_reward_and_persistent_completion_in_same_state(self):
        text='CityObjective obj("Tower"); Job save("SuperBuild_Saves.Tower");\nState Build() { CityObjective_SetComplete(obj); save.SetValue("nState",2); }'
        self.assertEqual(pairs(text),{('SuperBuild_Saves.Tower','Tower')})
        self.assertEqual(pairs(text.replace('save.SetValue','}\nState Other() { save.SetValue')),set())
