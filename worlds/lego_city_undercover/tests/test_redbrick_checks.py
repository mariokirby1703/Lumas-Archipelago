import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from client_checks import changed_checks
from level_progress import parse_level_progress,completed_level_keys
from red_bricks import redbrick_location_key
import json


class RedBrickTests(unittest.TestCase):
    def test_mansion_sources_and_saved_flags_are_separate(self):
        for number in (1,2):
            source=f'GAME6/levels/standalones/blackwells_mansion/mansion{number}_cave/room.giz:100:1'
            expected=f'mission:blackwells_mansion_{number}:Red Brick'
            self.assertEqual(redbrick_location_key(source),expected)
            descriptor=bytearray(128);path=b'Standalones\\Blackwells_Mansion';descriptor[:len(path)]=path
            name=f'Blackwells_Mansion_{number}'.encode();descriptor[64:64+len(name)]=name
            raw=bytearray(20);raw[9]=2
            row=parse_level_progress(descriptor,raw,number)
            self.assertEqual(completed_level_keys(dict(status='read',records=[row])),{expected})
        self.assertIsNone(redbrick_location_key('GAME6/levels/standalones/blackwells_mansion/unknown/room.giz:1:1'))

    def test_catalogue_has_no_phantom_and_covers_all_bound_red_sources(self):
        world=Path(__file__).resolve().parents[1]
        catalogue=json.loads((world/'catalogue.json').read_text())['locations']
        self.assertNotIn('mission:police_station:Red Brick',catalogue)
        self.assertNotIn('mission:blackwells_mansion:Red Brick',catalogue)
        for number in (1,2):self.assertIn(f'mission:blackwells_mansion_{number}:Red Brick',catalogue)
        sources=json.loads((world/'bridge/city_pickup_sources.json').read_text())
        for source in sources:
            if source.get('native_type')!=7:continue
            key=redbrick_location_key(source['source_key'])
            if not key:continue
            with self.subTest(source=source['source_key']):
                self.assertIn(key,catalogue)
                self.assertEqual(catalogue[key]['category'],'red_bricks')
                row=catalogue[key]
                snapshot=dict(objectives=dict(records=[]),pickup_bits=[],native_pickups=dict(status='read',objects=[
                    dict(source_key=source['source_key'],native_type=7,native_collected=True)]))
                self.assertEqual(changed_checks({str(row['id']):dict(row,key=key)},None,snapshot)[0],[row['id']])

    def test_city_pickup_uses_unique_native_identity(self):
        source='GAME5/levels/lego_city/lego_city/wi_forest/wi_forest_0701/wi_forest_0701.giz:1018:2'
        catalogue={'1':dict(key='source_pickup:'+source)}
        obj=dict(source_key=source,native_type=7,native_collected=True)
        snapshot=dict(objectives=dict(records=[]),pickup_bits=[],native_pickups=dict(status='read',objects=[obj]))
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[1])
        self.assertEqual(changed_checks(catalogue,None,snapshot,{1})[0],[])
        obj['native_collected']=False
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[])

    def test_story_pickup_reports_existing_grouped_location_only(self):
        source='GAME6/levels/standalones/prison/room/room.giz:123:1'
        catalogue={'1':dict(key='mission:prison:Red Brick'),'2':dict(key='source_pickup:'+source),
                   '3':dict(key='mission:mine:Red Brick')}
        snapshot=dict(objectives=dict(records=[]),pickup_bits=[],native_pickups=dict(status='read',objects=[
            dict(source_key=source,native_type=7,native_collected=True)]))
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[1])
        snapshot['native_pickups']['objects'][0]['source_key']=None
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[])

    def test_saved_redbrick_does_not_require_mission_completion(self):
        descriptor=bytearray(128);descriptor[:18]=b'Standalones\\Prison'
        raw=bytearray(20);raw[9]=2
        row=parse_level_progress(descriptor,raw,2)
        keys=completed_level_keys(dict(status='read',records=[row]))
        self.assertIn('mission:prison:Red Brick',keys)
        self.assertNotIn('mission:prison:Complete',keys)
