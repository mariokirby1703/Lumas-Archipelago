import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from story_points import POINTS,COMPLETIONS,catalogue_rows,completed_story_points
from client_checks import changed_checks
from client_journal import Journal

class StoryPointTests(unittest.TestCase):
    def test_every_sheet_point_is_reviewed_without_start_event_checks(self):
        self.assertEqual(len(POINTS),150);self.assertEqual(len(COMPLETIONS),14)
        self.assertEqual(sum(r['kind']=='existing_location' for r in POINTS),35)
        self.assertEqual({r['chapter'] for r in POINTS},set(range(1,16))|{None})
        for row in POINTS:
            if row['kind'] in ('internal_control_event','entry_control_event','unresolved'):
                self.assertFalse(row['check_eligible']);self.assertIsNotNone(row['todo'])
            self.assertFalse(row['write_safe'])
    def test_chapter_selection_assignment_completion_or_ap_ownership_is_not_a_story_check(self):
        story=dict(status='read',jobs={'Flow_Setup':dict(Flow_Act=4), 'Flow_Setup.Act_4':dict(Act4_Mission=15)})
        self.assertEqual(completed_story_points(story),set())
        catalogue={str(v['id']):dict(key=k,**v) for k,v in catalogue_rows().items()}
        snap=dict(objectives=dict(records=[]),pickup_bits=[],story=story,
            characters=[dict(found_bit=False,owned_byte=1,internal_name='COP',group='character')])
        self.assertEqual(changed_checks(catalogue,None,snap)[0],[])
    def test_each_explicit_boolean_reconciles_independently_and_journal_survives_reconnect(self):
        for row in COMPLETIONS:
            for value,expected in ((False,False),(1,False),(True,True)):
                story=dict(status='read',jobs={row['job']:{row['field']:value}})
                self.assertEqual(row['ap_key'] in completed_story_points(story),expected)
        row=COMPLETIONS[0];entry=catalogue_rows()[row['ap_key']]
        catalogue={str(row['ap_id']):dict(key=row['ap_key'],**entry)}
        snap=dict(objectives=dict(records=[]),pickup_bits=[],story=dict(status='read',jobs={row['job']:{row['field']:True}}))
        checks,_=changed_checks(catalogue,None,snap);self.assertEqual(checks,[row['ap_id']])
        with tempfile.TemporaryDirectory() as directory:
            binding=dict(seed='story',slot=1)
            with closing(Journal(Path(directory),binding)) as j:j.queue(checks)
            with closing(Journal(Path(directory),binding)) as j:
                self.assertEqual(j.pending(),checks);j.acknowledge(checks)
                self.assertEqual(changed_checks(catalogue,None,snap,checks)[0],[])
    def test_new_ids_are_source_based_and_schema_typed(self):
        root=Path(__file__).resolve().parents[1]
        catalogue=json.loads((root/'catalogue.json').read_text())['locations']
        ids={r['id'] for r in catalogue.values()};self.assertEqual(len(ids),len(catalogue))
        for row in COMPLETIONS:
            self.assertEqual(catalogue[row['ap_key']]['id'],row['ap_id'])
            self.assertTrue(row['evidence']);self.assertTrue(all(e['value'] and e['state'] for e in row['evidence']))
            self.assertFalse(catalogue[row['ap_key']]['logic_verified'])
