import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from worlds.lego_city_undercover import CATALOGUE
from worlds.lego_city_undercover.bridge.location_design import data
from worlds.lego_city_undercover.bridge.source_logic import source_rule
from worlds.lego_city_undercover.bridge.station_rewards import GRACE_REWARD_KEY
from worlds.lego_city_undercover.bridge.research_profile import symbol_hash


class DesignTests(unittest.TestCase):
    def test_all_sheet_rows_preserved_without_claiming_native_requirements(self):
        design=data('location_design.json');self.assertEqual(len(design['rows']),866)
        self.assertFalse(design['requirements_verified'])
        self.assertEqual(sum(r['native_match']=='exact_key' for r in design['rows']),597)
        for r in design['rows']:self.assertIn('unverified_user_design',r['design']['evidence'])

    def test_cop_wardrobe_reward_is_retired_only_for_new_generation(self):
        self.assertIn(GRACE_REWARD_KEY,CATALOGUE['locations'])
        relation=CATALOGUE['locations'][GRACE_REWARD_KEY]['token_relationship']
        self.assertTrue(relation['exclude_from_new_generation']);self.assertEqual(relation['classification'],'story_reward')
    def test_police_hub_descriptors_are_not_a_sixteenth_special_assignment(self):
        rows=[r for k,r in CATALOGUE['locations'].items() if k.startswith('mission:police_station:')]
        self.assertEqual(len(rows),7)
        self.assertTrue(all(r.get('legacy_non_assignment_hub') for r in rows))
    def test_native_theft_reward_keeps_only_the_underlying_activity_in_new_seeds(self):
        from worlds.lego_city_undercover.tests.test_generation import GenerationTests
        from worlds.lego_city_undercover.bridge.client_checks import changed_checks
        _,world=GenerationTests().build()
        key='source_pickup:GAME5/levels/lego_city/lego_city/ny_uptown/ny_uptown_1604/ny_uptown_1604.giz:1066:1'
        self.assertIn(key,CATALOGUE['locations']);self.assertNotIn(key,world.active_catalogue)
        row=CATALOGUE['locations'][key]['token_relationship']
        self.assertEqual(row['automatic_reward_sources'],['objective:NY_UT_1604_CarTheft'])
        catalogue={str(r['id']):dict(key=k,**r) for k,r in world.active_catalogue.items()}
        snapshot=dict(objectives=dict(records=[dict(name_hash=symbol_hash('NY_UT_1604_CarTheft'),candidate_complete=True)]),
            pickup_bits=[],characters=[dict(internal_name='SMALLCARS_SMALLISIMO',group='vehicle',found_bit=True)])
        ident=world.active_catalogue['objective:NY_UT_1604_CarTheft']['id']
        self.assertEqual(changed_checks(catalogue,None,snapshot)[0],[ident])
        self.assertEqual(changed_checks(catalogue,None,snapshot,{ident})[0],[])

    def test_distinct_aura_requirements_do_not_collapse_to_generic_scanner(self):
        class State:
            def __init__(self,names):self.names=names
            def has(self,name,player,*args):return name in self.names
        police=State({'Ability: Police','Ability: Scanner'})
        self.assertTrue(source_rule(dict(native_type='COP_CriminalScan'),1)(police))
        self.assertFalse(source_rule(dict(native_type='COP_AudioScan'),1)(police))
        self.assertTrue(source_rule(dict(native_type='COP_AudioScan'),1)(State({'Ability: Police','Ability: Wiretap'})))

    def test_unknown_build_category_does_not_invent_construction_or_superbuild_lock(self):
        class EmptyState:
            def has(self,*args):return False
        self.assertTrue(source_rule(dict(category='super_builds',native_type='SuperBuild'),1)(EmptyState()))
        self.assertTrue(source_rule(dict(design_requirements=dict(classes='Construction Worker')),1)(EmptyState()))
