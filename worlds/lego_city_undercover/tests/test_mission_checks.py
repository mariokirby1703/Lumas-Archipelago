from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge'))
from mission_checks import completed_shield_locations, shield_locations, PARTS
from mission_checks import decode_shield_mask
from mission_checks import hero_complete,read_mission_hero
from client_checks import changed_checks


class MissionShieldTests(unittest.TestCase):
    def test_city_hero_uses_native_latch_and_level_target(self):
        self.assertTrue(hero_complete(90000,90000,1))
        self.assertFalse(hero_complete(90000,90000,0))
        self.assertFalse(hero_complete(89999,90000,1))
        self.assertFalse(hero_complete(90000,0,1))
        for values in ((-1,90000,1),(90000,90000,2),(True,90000,1)):
            with self.assertRaises(ValueError):hero_complete(*values)
        catalogue={'1':dict(key='mission:mine:LEGO City Hero'),
                   '2':dict(key='mission:prison:LEGO City Hero')}
        snapshot=dict(objectives=dict(records=[]),pickup_bits=[],
                      mission_hero=dict(status='read',mission='mine',complete=True))
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[1])
        self.assertEqual(changed_checks(catalogue,None,snapshot,{1})[0],[])
        snapshot['mission_hero']['status']='unresolved'
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[])

    def test_hero_threshold_reader_mirrors_native_table_path(self):
        from unittest.mock import patch
        import struct
        base=0;level=0x1000;meta=0x2000;table=0x3000
        memory={level+0x18:struct.pack('<Q',meta),0x1C7E61C:struct.pack('<i',0),
                0x1C7E608:struct.pack('<I',0),0x1C7EB60:struct.pack('<I',0),
                meta+0xAB:b'\x04',0x1C7D438:struct.pack('<i',16),
                0x1C7D430:struct.pack('<Q',table),table+4*0x350+0x190:struct.pack('<I',90000),
                0x1C7E6E0:struct.pack('<QI',90000,1)}
        def read(address,size):
            value=memory[address];self.assertEqual(len(value),size);return value
        with patch('scene_reader.player_scene',return_value=dict(level=level)):
            result=read_mission_hero(read,base,dict(status='read',mission='mine',scene='mine_tunnel'))
        self.assertTrue(result['complete']);self.assertEqual(result['threshold'],90000)

    def test_native_tr_mask_maps_only_current_mission(self):
        self.assertEqual(decode_shield_mask(2),['TR'])
        catalogue={'1':dict(key='mission:mine:TR'),'2':dict(key='mission:prison:TR'),
                   '3':dict(key='mission:mine:Police Shield')}
        snapshot=dict(objectives=dict(records=[]),pickup_bits=[],
                      mission_shield=dict(status='read',mission='mine',mask=2,parts=['TR']))
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[1])
        self.assertEqual(changed_checks(catalogue,None,snapshot,{1})[0],[])
        snapshot['mission_shield'].update(mask=15,parts=list(PARTS))
        self.assertEqual(changed_checks({'3':catalogue['3']},None,snapshot)[0],[3])
        snapshot['mission_shield']['status']='unresolved_scene'
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[])
        for mask in (-1,16,True):
            with self.assertRaises(ValueError):decode_shield_mask(mask)

    def test_whole_requires_four_distinct_parts(self):
        self.assertEqual(completed_shield_locations('SA1', 'whole', ['TL']*4), ())
        self.assertEqual(len(completed_shield_locations('SA1', 'whole', PARTS)), 1)

    def test_quarters_never_add_whole_check(self):
        self.assertEqual(len(shield_locations('SA1', 'quarters')), 4)
        result = completed_shield_locations('SA1', 'quarters', ['TL', 'BR'])
        self.assertEqual(result, ('SA1: Police Shield TL', 'SA1: Police Shield BR'))
        self.assertNotIn('SA1: Police Shield', completed_shield_locations('SA1', 'quarters', PARTS))

    def test_invalid_input_rejected(self):
        for mode in ('both', '', 'unknown'):
            with self.assertRaises(ValueError):
                shield_locations('SA1', mode)
        with self.assertRaises(ValueError):
            completed_shield_locations('SA1', 'quarters', ['unknown'])
