import unittest
from argparse import Namespace
from BaseClasses import MultiWorld, CollectionState
from worlds.lego_city_undercover import LCUWorld, TOKEN, CATALOGUE
from Fill import distribute_items_restrictive


class GenerationTests(unittest.TestCase):
    def test_experimental_area_seed_starts_auburn_and_places_first_pass_there(self):
        multi,world=self.build(dict(area_pass_items=True,experimental_area_restrictions=True,
                                    early_criminal_scan=True,early_detective_scan=True))
        state=CollectionState(multi)
        self.assertTrue(multi.get_region('District: SF_Docks',1).can_reach(state))
        self.assertFalse(multi.get_region('District: SF_Residential',1).can_reach(state))
        passes=[l for l in multi.get_locations(1) if l.item and l.item.name=='Area Pass: SF_Residential']
        self.assertEqual(len(passes),1);self.assertTrue(passes[0].can_reach(state))
        state.collect(passes[0].item,True)
        self.assertTrue(multi.get_region('District: SF_Residential',1).can_reach(state))
        self.assertFalse(any(i.name=='Area Pass: SF_Docks' for i in multi.itempool))
        self.assertTrue(world.fill_slot_data()['native_area_rollback'])
        distribute_items_restrictive(multi);self.assertTrue(multi.can_beat_game())

    def test_chronological_test_yaml_places_criminal_scan_before_police_gate(self):
        import yaml
        from pathlib import Path
        config=yaml.safe_load((Path(__file__).resolve().parents[1]/'docs/LCU_Chronological_Test.yaml').read_text())
        multi,world=self.build(config[LCUWorld.game])
        distribute_items_restrictive(multi)
        scanner=[loc for loc in multi.get_locations(1) if loc.item and loc.item.name=='Ability: Scanner']
        self.assertEqual(len(scanner),1)
        self.assertTrue(scanner[0].can_reach(CollectionState(multi)))
        self.assertEqual(scanner[0].parent_region.name,'Opening before Police')
        detective=[loc for loc in multi.get_locations(1) if loc.item and loc.item.name=='Ability: Detective Scan']
        self.assertEqual(len(detective),1)
        self.assertTrue(detective[0].can_reach(CollectionState(multi)))
        self.assertEqual(detective[0].parent_region.name,'Opening before Police')
        self.assertIsNotNone(world.early_police_location)
        self.assertTrue(multi.can_beat_game())

    def test_disabled_detective_lock_does_not_add_a_dead_item(self):
        multi,_=self.build({'detective_scan_lock':False})
        self.assertFalse(any(item.name=='Ability: Detective Scan' for item in multi.itempool))

    def test_early_criminal_scan_rejects_missing_pool_or_insufficient_opening_checks(self):
        with self.assertRaisesRegex(ValueError,'requires ability_items'):
            self.build({'early_criminal_scan':True,'ability_items':False})
        with self.assertRaisesRegex(ValueError,'local Scanner'):
            self.build({'early_criminal_scan':True,'non_local_items':{'Ability: Scanner'}})
        from worlds.lego_city_undercover.bridge.opening_logic import NO_POLICE_KEYS
        names={r['name'] for k,r in CATALOGUE['locations'].items() if k in NO_POLICE_KEYS}
        target=CATALOGUE['locations']['story_arrest:clown_1']['name']
        with self.assertRaisesRegex(ValueError,'both Police and Scanner'):
            self.build({'early_criminal_scan':True,'exclude_locations':names-{target}})

    def test_requested_packages_and_skin_classification(self):
        from BaseClasses import ItemClassification
        multi,world=self.build()
        names=[item.name for item in multi.itempool]
        self.assertEqual(names.count('Super Bricks 10,000'),5)
        self.assertEqual(names.count('Super Bricks 1,000'),20)
        self.assertEqual(world.create_item('Super Bricks 10,000').classification,ItemClassification.useful)
        self.assertEqual(world.create_item('Character: MINER').classification,ItemClassification.progression)
        for name in ('Studs 1,000','Studs 10,000','Studs 100,000','Super Bricks 100','Super Bricks 250'):
            self.assertEqual(world.create_item(name).classification,ItemClassification.filler)
        self.assertEqual(len(names),len(multi.get_unfilled_locations()))

    def build(self,changes=None):
        multi=MultiWorld(1);multi.game[1]=LCUWorld.game;multi.player_name={1:'LCUTest'};multi.set_seed(1234)
        args=Namespace()
        for name,option in LCUWorld.options_dataclass.type_hints.items():
            setattr(args,name,{1:option.from_any((changes or {}).get(name,option.default))})
        multi.set_options(args);multi.state=CollectionState(multi);world=multi.worlds[1]
        world.generate_early();world.create_regions();world.create_items();world.pre_fill()
        return multi,world

    def test_default_fill_and_goal(self):
        multi,world=self.build()
        self.assertEqual(len(multi.itempool),len(multi.get_unfilled_locations()))
        distribute_items_restrictive(multi)
        self.assertTrue(multi.can_beat_game())
        self.assertTrue(world.fill_slot_data()['native_grants'])
        self.assertFalse(world.fill_slot_data()['native_locks'])
        self.assertEqual(world.fill_slot_data()['native_reward_suppression'],'poll_after_checks')
        self.assertNotIn('unverified_clues',{r['category'] for r in world.active_catalogue.values()})

    def test_whole_and_quarters_are_exclusive(self):
        for value,included,excluded in ((1,'whole_shields','shield_quarters'),(2,'shield_quarters','whole_shields')):
            _,world=self.build({'police_shields':value})
            categories={r['category'] for r in world.active_catalogue.values()}
            self.assertIn(included,categories);self.assertNotIn(excluded,categories)

    def test_unverified_opt_in_and_ids(self):
        _,world=self.build({'include_unverified':True})
        expected={k for k,r in CATALOGUE['locations'].items() if r['category']!='whole_shields' and not r.get('legacy_aggregate') and not r.get('legacy_non_assignment_hub') and not r.get('token_relationship',{}).get('exclude_from_new_generation')}
        self.assertEqual(set(world.active_catalogue),expected)
        self.assertEqual(len(LCUWorld.item_name_to_id),len(set(LCUWorld.item_name_to_id.values())))
    def test_linear_police_is_guaranteed_on_an_opening_check(self):
        from worlds.lego_city_undercover.bridge.opening_logic import NO_POLICE_KEYS,POLICE_ITEMS
        multi,world=self.build()
        state=CollectionState(multi)
        for key,row in world.active_catalogue.items():
            if key in NO_POLICE_KEYS:self.assertTrue(multi.get_location(row['name'],1).can_reach(state))
        location=multi.get_location(world.early_police_location,1)
        self.assertTrue(location.locked)
        self.assertIn(location.item.name,POLICE_ITEMS)
        self.assertTrue(location.can_reach(state))
        state.collect(location.item,True)
        self.assertFalse(multi.get_region('Assignment 1: rooftops',1).can_reach(state))
        for item in multi.itempool:
            if item.advancement:state.collect(item,True)
        self.assertTrue(all(loc.can_reach(state) for loc in multi.get_locations(1)))
    def test_open_world_keeps_source_requirements_without_local_police_placement(self):
        multi,world=self.build({'story_mode':'open_world'})
        self.assertIsNone(world.early_police_location)
        state=CollectionState(multi)
        self.assertTrue(multi.get_region('LEGO City',1).can_reach(state))
        self.assertFalse(multi.get_region('Assignment 1: rooftops',1).can_reach(state))
    def test_character_only_pool_can_supply_opening_police(self):
        multi,world=self.build({'ability_items':False})
        self.assertEqual(multi.get_location(world.early_police_location,1).item.name,'Character: COP')
    def test_linear_generation_rejects_missing_police_instead_of_an_unbeatable_seed(self):
        with self.assertRaisesRegex(ValueError,'requires Police'):
            self.build({'ability_items':False,'character_items':False})
    def test_opening_police_respects_excluded_locations(self):
        from worlds.lego_city_undercover.bridge.opening_logic import NO_POLICE_KEYS
        names={r['name'] for k,r in CATALOGUE['locations'].items() if k in NO_POLICE_KEYS}
        target=CATALOGUE['locations']['story_arrest:clown_1']['name']
        multi,world=self.build({'exclude_locations':names-{target}})
        self.assertEqual(world.early_police_location,target)
        with self.assertRaisesRegex(ValueError,'no enabled opening location'):
            self.build({'exclude_locations':names})
    def test_linear_police_does_not_silently_override_non_local_items(self):
        with self.assertRaisesRegex(ValueError,'local opening Police'):
            self.build({'non_local_items':{'Ability: Police','Character: COP'}})
