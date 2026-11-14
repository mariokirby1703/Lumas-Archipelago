import json
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from story_arrests import ARRESTS,completed_story_arrests
from client_checks import changed_checks

class StoryArrestTests(unittest.TestCase):
    def snapshot(self,**flags):
        return dict(objectives=dict(records=[]),pickup_bits=[],
                    story=dict(status='read',jobs={'Flow_Setup.Flow_Completed':flags}))
    def catalogue(self):
        return {str(i):dict(key=r['key'],status='native_story_flag',runtime=dict(kind='story_arrest'))
                for i,r in enumerate(ARRESTS,1)}
    def test_each_arrest_has_its_own_persistent_check(self):
        for i in range(1,4):
            snapshot=self.snapshot(**{f'Act_1_CatchRobber_{i}':True})
            self.assertEqual(changed_checks(self.catalogue(),None,snapshot)[0],[i])
    def test_offline_completion_reconciles_on_first_snapshot_and_respects_acknowledgements(self):
        snapshot=self.snapshot(**{r['field']:True for r in ARRESTS})
        self.assertEqual(changed_checks(self.catalogue(),None,snapshot)[0],[1,2,3])
        self.assertEqual(changed_checks(self.catalogue(),None,snapshot,{1,3})[0],[2])
        self.assertEqual(changed_checks({},None,snapshot)[0],[])
    def test_missing_invalid_or_other_story_flags_never_count(self):
        for value in (False,None,1,'true'):
            self.assertEqual(completed_story_arrests(self.snapshot(Act_1_CatchRobber_1=value)['story']),set())
        self.assertEqual(completed_story_arrests({'status':'unresolved','jobs':{}}),set())
        self.assertEqual(changed_checks(self.catalogue(),None,self.snapshot(Act_1_GoToPoliceStation=True))[0],[])
    def test_generated_catalogue_binds_exactly_three_arrests(self):
        path=Path(__file__).resolve().parents[1]/'catalogue.json'
        locations=json.loads(path.read_text())['locations']
        rows=[r for r in locations.values() if (r.get('runtime') or {}).get('kind')=='story_arrest']
        self.assertEqual(len(rows),3)
        self.assertEqual({r['runtime']['field'] for r in rows},{r['field'] for r in ARRESTS})
        self.assertTrue(all(r['category']=='story_missions' for r in rows))
