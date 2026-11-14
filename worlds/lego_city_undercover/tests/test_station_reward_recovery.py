from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from station_rewards import COP_REWARD_KEY,GRACE_REWARD_KEY,completed_station_rewards,grace_reward_metadata
from client_checks import changed_checks


class StationRewardRecoveryTests(unittest.TestCase):
    def snapshot(self,acquired=None):
        return dict(objectives=dict(status='read',records=[]),pickup_bits=[],characters=[],
                    story=dict(status='read',jobs={'PDA':{'acquired':acquired}}))

    def catalogue(self,legacy=False):
        return {'1':dict(key=COP_REWARD_KEY,status='experimental_model_found',runtime=dict(kind='model_found',native_name='COP')),
                '2':dict(key=GRACE_REWARD_KEY,**(dict(status='experimental_model_found',runtime=dict(kind='model_found',native_name='COP'))
                                              if legacy else grace_reward_metadata()))}

    def test_police_ownership_and_wardrobe_build_alone_are_not_checks(self):
        snapshot=self.snapshot(False)
        snapshot['characters']=[dict(internal_name='COP',group='character',owned_byte=1,found_bit=False)]
        self.assertEqual(changed_checks(self.catalogue(),None,snapshot)[0],[])
        snapshot['story']['status']='not_initialized'
        snapshot['story']['jobs']['PDA']['acquired']=True
        self.assertFalse(completed_station_rewards(snapshot['story']))

    def test_completed_garage_recovers_old_seed_and_new_grace_check(self):
        for legacy in (True,False):
            self.assertEqual(changed_checks(self.catalogue(legacy),None,self.snapshot(True))[0],[1,2])
            self.assertEqual(changed_checks(self.catalogue(legacy),None,self.snapshot(True),{1,2})[0],[])
            self.assertEqual(changed_checks(self.catalogue(legacy),None,self.snapshot(True),{1})[0],[2])

    def test_new_seed_genuine_grace_discovery_has_its_own_source(self):
        snapshot=self.snapshot(False)
        snapshot['characters']=[dict(internal_name='COP_FEMALE_P2',group='character',found_bit=True)]
        self.assertEqual(changed_checks(self.catalogue(),None,snapshot)[0],[2])

    def test_recovery_does_not_invent_locations_disabled_in_seed(self):
        self.assertEqual(changed_checks({},None,self.snapshot(True))[0],[])
