import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from activity_rewards import ACTIVITY_REWARDS,completed_activity_rewards
from client_checks import changed_checks

class ActivityRewardTests(unittest.TestCase):
    def snapshot(self,**changes):
        reward=ACTIVITY_REWARDS[0]
        row=dict(tile_name=reward['scene'],name=reward['pickup_name'],native_type=11,native_collected=True)
        row.update(changes)
        return dict(objectives=dict(status='read',records=[]),pickup_bits=[],native_pickups=dict(status='read',objects=[row]))
    def test_completed_ride_is_one_check_not_generic_gold_count(self):
        reward=ACTIVITY_REWARDS[0]
        catalogue={'123':dict(key='source_pickup:'+reward['source_key'],status='verified_activity_reward',
                            runtime=dict(kind='activity_reward',reward_key=reward['key']))}
        snapshot=self.snapshot();snapshot['gold_bricks']=999
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[123])
        self.assertEqual(changed_checks(catalogue,None,snapshot,{123})[0],[])
        self.assertEqual(changed_checks(catalogue,None,self.snapshot(native_collected=False))[0],[])
    def test_wrong_room_type_source_or_duplicate_object_cannot_complete(self):
        for change in (dict(tile_name='Lego_City'),dict(native_type=12),dict(source_key='other'),dict(name='GB_Other')):
            self.assertFalse(completed_activity_rewards(self.snapshot(**change)))
        snapshot=self.snapshot();snapshot['native_pickups']['objects']*=2
        self.assertFalse(completed_activity_rewards(snapshot))
    def test_generated_catalogue_contains_named_activity_without_duplicate_clues(self):
        world=Path(__file__).resolve().parents[1]
        catalogue=json.loads((world/'catalogue.json').read_text())['locations'];reward=ACTIVITY_REWARDS[0]
        location=catalogue['source_pickup:'+reward['source_key']]
        self.assertEqual(location['name'],reward['name'])
        self.assertEqual(location['category'],'city_activities')
        for name in reward['prerequisite_objectives']:self.assertNotIn('objective:'+name,catalogue)
