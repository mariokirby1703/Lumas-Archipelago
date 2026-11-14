import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from progressive_items import resolve_receipts
from item_delivery import effect_plan
from class_entitlements import model_class_ready
from capabilities import pool_candidates, supported_effect
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
        effects={str(i):dict(name=name,category='progressive' if name=='Progressive Astronaut' else 'ability')
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
