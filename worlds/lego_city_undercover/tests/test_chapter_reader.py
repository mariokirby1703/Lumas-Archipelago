import struct
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from chapter_reader import read_chapter_events,parse_chapter_mask
from snapshot_guard import snapshot_identity,verify_snapshot_identity

class ChapterReaderTests(unittest.TestCase):
    def test_event_bank_is_observation_only_and_does_not_invent_active_chapter(self):
        manager=0x20000;profile=0x30000
        pointers={0x1C7F160:profile,0x17EBD00:manager,manager:0xC10988}
        with patch('chapter_reader.pointer',side_effect=lambda r,a:pointers[a]):
            result=read_chapter_events(lambda a,n:struct.pack('<I',6 if a==manager+0x110 else 0),0)
        self.assertEqual(result['reported_completed'],[[1,2],[]])
        self.assertIsNone(result['active_chapter']);self.assertFalse(result['check_eligible'])
        self.assertFalse(result['native_save_isolation_verified'])
    def test_unknown_class_or_switching_profile_is_rejected(self):
        with patch('chapter_reader.pointer',side_effect=[0x30000,0x20000,0xBAD]):
            with self.assertRaises(ValueError):read_chapter_events(lambda a,n:bytes(n),0)
        self.assertEqual(parse_chapter_mask(1<<15),[15])
        with self.assertRaises(ValueError):parse_chapter_mask(-1)
    def test_late_story_read_cannot_escape_the_final_snapshot_identity_guard(self):
        state=dict(profile=123,actor=456,world=789,marker={'binding':'ours'})
        def pointer(read,address):return state[{0x1C7F160:'profile',0x1C7D3E0:'actor',0x1C6A768:'world'}[address]]
        with patch('snapshot_guard.pointer',side_effect=pointer),patch('snapshot_guard.read_marker',side_effect=lambda *args:dict(state['marker'])):
            expected=snapshot_identity(None,0);verify_snapshot_identity(expected,None,0)
            for field,replacement in [('profile',999),('actor',888),('world',777),('marker',{'binding':'other'})]:
                old=state[field];state[field]=replacement
                with self.assertRaises(RuntimeError):verify_snapshot_identity(expected,None,0)
                state[field]=old
