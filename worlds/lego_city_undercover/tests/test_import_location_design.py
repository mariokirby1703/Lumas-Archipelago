import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from import_location_design import parse_design
class SheetHeaderTests(unittest.TestCase):
    def test_reordered_english_headers_preserve_exact_identity_and_unverified_tools(self):
        cat=dict(locations={'mission:test:Complete':dict(id=123)})
        values=[['AP Key / Source','Location / Check','Area','No.','Category','Tools','Build Cost ??'],
                ['mission:test:Complete','Test complete','Auburn',1,'Story Mission','Grapple Gun',0]]
        row=parse_design(values,cat)[0]
        self.assertEqual(row['native_key'],'mission:test:Complete');self.assertEqual(row['native_match'],'exact_key')
        self.assertEqual(row['design']['tools'],'Grapple Gun');self.assertEqual(row['design']['classes'],'')
        self.assertEqual(row['design']['building_bricks'],0);self.assertEqual(cat['locations'][row['native_key']]['id'],123)
    def test_german_legacy_headers_and_missing_identity_fail_closed(self):
        values=[['Nr.','Kategorie','Area','Check / Aufgabe','AP-Key / Source','Verkleidung(en)'],[1,'Test','Auburn','Name','unknown','Polizei']]
        self.assertEqual(parse_design(values,dict(locations={}))[0]['native_match'],'unmatched')
        values[0][4]='Unknown'
        with self.assertRaises(ValueError):parse_design(values,dict(locations={}))
