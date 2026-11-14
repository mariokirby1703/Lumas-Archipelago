import json
from pathlib import Path
import sys
import unittest

WORLD=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from pickup_reader import attach_source_identities
from client_checks import changed_checks


class MissionSuperbrickCoverageTests(unittest.TestCase):
    def test_every_catalogued_mission_superbrick_has_unique_runtime_binding(self):
        catalogue=json.loads((WORLD/'catalogue.json').read_text())['locations']
        sources=json.loads((WORLD/'bridge/city_pickup_sources.json').read_text())
        missions=set();count=0
        for key,row in catalogue.items():
            if row['category']!='super_bricks' or '/levels/standalones/' not in row['source']:continue
            count+=1
            mission=row['source'].split('/standalones/')[1].split('/')[0];missions.add(mission)
            source_key=key.removeprefix('source_pickup:')
            source=next(s for s in sources if s['source_key']==source_key)
            with self.subTest(source=source_key):
                # Also accept the native scene spelling used by tech resources.
                obj=dict(name=source['name'],tile_name=source['tile_name']+'_tech',
                         native_type=source['native_type'],native_collected=True)
                native=attach_source_identities(dict(status='read',objects=[obj]),sources)
                self.assertEqual(obj['source_key'],source_key)
                snapshot=dict(objectives=dict(records=[]),pickup_bits=[],native_pickups=native)
                active={str(row['id']):dict(row,key=key)}
                self.assertEqual(changed_checks(active,None,snapshot)[0],[row['id']])
                obj['native_collected']=False
                self.assertEqual(changed_checks(active,None,snapshot)[0],[])
                obj['native_type']=0
                attach_source_identities(native,sources)
                self.assertIsNone(obj['source_key'])
        self.assertGreater(count,0)
        self.assertIn('mine',missions);self.assertIn('prison',missions)

    def test_parent_resource_variants_remain_ambiguous(self):
        sources=[dict(tile_name=scene,name='P_pup',native_type=12,source_key=key)
                 for scene,key in [('level','a'),('level_tech','b')]]
        obj=dict(tile_name='level',name='P_pup',native_type=12)
        attach_source_identities(dict(objects=[obj]),sources)
        self.assertIsNone(obj['source_key'])
        self.assertEqual(obj['source_candidates'],['a','b'])
