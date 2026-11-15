import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from progressive_items import resolve_receipts,PROGRESSIVE_FAMILIES
from item_delivery import effect_plan
from class_entitlements import model_class_ready
from capabilities import pool_candidates, supported_effect,has_capability
from reward_policy import reward_masks


class ProgressiveItemsTests(unittest.TestCase):
    def test_progressive_manages_both_stages_but_only_entitles_resolved_stage(self):
        models={'ASTRONAUT':1};effect=dict(name='Progressive Astronaut',category='progressive')
        masks=reward_masks([effect],[dict(name='Ability: Astronaut',category='ability')],models,[],{'ability_items':1})
        from research_profile import ABILITY_NAMES
        self.assertEqual(masks['entitled_models'],{1})
        self.assertIn(ABILITY_NAMES.index('Jetpack'),masks['managed_abilities'])
        self.assertNotIn(ABILITY_NAMES.index('Jetpack'),masks['entitled_abilities'])

    def resolve(self,names):
        effects={str(i):dict(name=name,category='progressive' if name in PROGRESSIVE_FAMILIES else 'ability')
                 for i,name in enumerate(dict.fromkeys(names))}
        lookup={v['name']:int(k) for k,v in effects.items()}
        receipts=[SimpleNamespace(item=lookup[name]) for name in names]
        return [effect_plan(e) for _,_,e in resolve_receipts(receipts,effects)]

    def test_order_and_duplicates_are_receipt_deterministic(self):
        names=['Progressive Astronaut']*3
        expected=[dict(kind='model_unlock',native_name='ASTRONAUT'),dict(kind='ability_unlock',ability='Jetpack'),
                  dict(kind='noop',reason='Progressive stages already entitled')]
        self.assertEqual(self.resolve(names),expected)
        self.assertEqual(self.resolve(names),self.resolve(names))
        self.assertEqual(self.resolve(names[:1]),expected[:1])

    def test_all_families_grant_exactly_two_stages_and_preserve_legacy_tools(self):
        for family,stages in PROGRESSIVE_FAMILIES.items():
            with self.subTest(family=family):
                plans=self.resolve([family]*3)
                self.assertEqual(plans[:2],[effect_plan(e) for e in stages])
                self.assertEqual(plans[2]['kind'],'noop')
                self.assertEqual(self.resolve([stages[0]['name'],family])[1],effect_plan(stages[1]))
                self.assertEqual(self.resolve([stages[1]['name'],family])[1],effect_plan(stages[0]))
        self.assertEqual(self.resolve(['Ability: EnergyGun','Progressive Robber'])[1],dict(kind='model_unlock',native_name='ROBBER'))

    def test_scans_require_first_police_stage_but_never_consume_a_stage(self):
        plans=self.resolve(['Ability: Scanner','Ability: Detective Scan','Ability: Wiretap','Progressive Police','Progressive Police'])
        self.assertEqual(plans[3],dict(kind='model_unlock',native_name='COP'))
        self.assertEqual(plans[4],dict(kind='ability_unlock',ability='GrappleGun'))
        class State:
            def __init__(self,names):self.names=names
            def has(self,name,player,count=1):return self.names.count(name)>=count
        for scan in ('Scanner','Detective Scan','Wiretap','Surveillance'):
            self.assertFalse(has_capability(State(['Ability: '+scan]),1,scan))
            self.assertTrue(has_capability(State(['Progressive Police','Ability: '+scan]),1,scan))
        self.assertFalse(has_capability(State(['Progressive Police']),1,'GrappleGun'))
        self.assertTrue(has_capability(State(['Progressive Police']*2),1,'GrappleGun'))

    def test_native_scan_entitlements_wait_for_police_and_do_not_grant_grapple(self):
        scans=[dict(name='Ability: '+name,category='ability') for name in ('Scanner','Detective Scan','Wiretap')]
        effects=[dict(name='Progressive Police',category='progressive'),*scans]
        options=dict(ability_items=True,detective_scan_lock=True,class_tool_prerequisites=True)
        locked=reward_masks(effects,scans,{'COP':227},[],options)
        self.assertEqual(locked['entitled_abilities'],set());self.assertEqual(locked['entitled_runtime'],set())
        unlocked=reward_masks(effects,[*scans,dict(name='Ability: Police',category='ability')],{'COP':227},[],options)
        from research_profile import ABILITY_NAMES
        self.assertIn(ABILITY_NAMES.index('Scanner'),unlocked['entitled_abilities'])
        self.assertNotIn(ABILITY_NAMES.index('GrappleGun'),unlocked['entitled_abilities'])
        self.assertEqual(unlocked['entitled_runtime'],{0})

    def test_legacy_start_inventory_consumes_matching_stage(self):
        self.assertEqual(self.resolve(['Ability: Astronaut','Progressive Astronaut'])[1],
                         dict(kind='ability_unlock',ability='Jetpack'))
        self.assertEqual(self.resolve(['Ability: Jetpack','Progressive Astronaut'])[1],
                         dict(kind='model_unlock',native_name='ASTRONAUT'))

    def test_cosmetic_class_entitlement_and_legacy_compatibility(self):
        skin='COP_FEMALE_P2'
        self.assertFalse(model_class_ready(skin,[],{'separate_class_unlocks':1}))
        self.assertTrue(model_class_ready(skin,[dict(name='Ability: Police',category='ability')],{'separate_class_unlocks':1}))
        self.assertTrue(model_class_ready(skin,[],{}))
        self.assertTrue(model_class_ready('COLLECT_1-15_DEEPSEADIVER',[],{'separate_class_unlocks':1}))

    def test_default_pool_has_supported_effects_without_class_aliases(self):
        from worlds.lego_city_undercover import CATALOGUE
        allowed=dict(character=True,vehicle=True,ability=True,cheat=True,area_pass=True,story_access=True)
        names=pool_candidates(CATALOGUE['items'],allowed)
        self.assertIn('Progressive Astronaut',names)
        for name in ('Ability: Astronaut','Ability: Jetpack','Character: COP','Character: ASTRONAUT','Ability: Carry Objects'):
            self.assertNotIn(name,names)
        for name in names:
            self.assertTrue(supported_effect(dict(CATALOGUE['items'][name],name=name)),name)
