"""Build bounded native reward suppression masks from seed options and receipts."""
import struct
from item_delivery import effect_plan
from research_profile import ABILITY_NAMES

POLICY=struct.Struct('<4I32I32I4Q4I')
assert POLICY.size==320
STARTING_MODELS=frozenset(('CIVILIAN_CHASEMCCAIN','CIVILIAN_CHASEMCCAIN_ALT'))
# Story/map/mission bookkeeping flags are not tool entitlements.
TOOL_ABILITIES=frozenset(('GrappleGun','EnergyGun','SuperBuild','Parkour','Grab','TargetThrow',
    'FinishingMove','Parry','Scanner','Camera','Surveillance','Wiretap','DataScanner','Snapshot',
    'Jetpack','FireAxe','Pigs','FastTravel','DisguiseBooth','Race','SuperStrength','2x_Brick_Multi'))


def reward_masks(effects,received,models,cheats,options):
    managed_models=set();entitled_models=set();managed_abilities=set();entitled_abilities=set()
    managed_cheats=set();entitled_cheats=set()
    cheat_ids={r['native_name']:r['index'] for r in cheats}
    def add(effect,entitled):
        category=effect.get('category')
        if not entitled and not options.get({'character':'character_items','vehicle':'vehicle_items','ability':'ability_items','cheat':'cheat_items'}.get(category,''),False):return
        plan=effect_plan(effect)
        if plan['kind']=='model_unlock':
            name=plan['native_name']
            if name in STARTING_MODELS or name not in models:return
            (entitled_models if entitled else managed_models).add(models[name])
        elif plan['kind']=='ability_unlock' and plan['ability'] in TOOL_ABILITIES:
            (entitled_abilities if entitled else managed_abilities).add(ABILITY_NAMES.index(plan['ability']))
        elif plan['kind']=='cheat_unlock' and plan.get('native_name') in cheat_ids:
            (entitled_cheats if entitled else managed_cheats).add(cheat_ids[plan['native_name']])
    for effect in effects:add(effect,False)
    for effect in received:add(effect,True)
    return dict(managed_models=managed_models,entitled_models=entitled_models&managed_models,
                managed_abilities=managed_abilities,entitled_abilities=entitled_abilities&managed_abilities,
                managed_cheats=managed_cheats,entitled_cheats=entitled_cheats&managed_cheats)


def encode_policy(pid,binding,masks):
    def words(values):
        result=[0]*32
        for value in values:
            if type(value) is not int or not 0<=value<1002:raise ValueError('Model policy outside pinned table')
            result[value//32]|=1<<(value%32)
        return result
    def bits(values,limit):
        if any(type(v) is not int or not 0<=v<limit for v in values):raise ValueError('Policy index outside table')
        return sum(1<<v for v in values)
    if len(binding)!=16:raise ValueError('Invalid policy binding')
    return POLICY.pack(0x4c435550,1,pid,0,*words(masks['managed_models']),*words(masks['entitled_models']),
        bits(masks['managed_abilities'],51),bits(masks['entitled_abilities'],51),
        bits(masks['managed_cheats'],40),bits(masks['entitled_cheats'],40),*struct.unpack('<4I',binding))
