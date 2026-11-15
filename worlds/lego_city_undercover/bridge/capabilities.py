"""Native-backed capabilities and aliases shared by generation and client.

This registry does not invent flags for composite actions. Such actions are
described as class/tool requirements; unsupported standalone items are opt-in.
"""
try:
    from .item_delivery import CLASS_MODELS,effect_plan
    from .research_profile import ABILITY_NAMES
except ImportError:
    from item_delivery import CLASS_MODELS,effect_plan
    from research_profile import ABILITY_NAMES

PROGRESSIVE_ASTRONAUT='Progressive Astronaut'
UNSUPPORTED_ABILITIES=frozenset(('Carry Objects','Climbing','Crowbar','Fishing','Stethoscope'))
NATIVE_TOOL_NAMES=frozenset(ABILITY_NAMES)
CLASS_CATEGORIES={1:'Police',2:'Robber',3:'Miner',4:'Astronaut',5:'Farmer',6:'Firefighter',7:'Construction Worker'}


def supported_effect(effect):
    if effect.get('name')==PROGRESSIVE_ASTRONAUT:return True
    plan=effect_plan(effect)
    if plan['kind']=='ability_unlock':return plan['ability'] in NATIVE_TOOL_NAMES
    return plan['kind'] in ('model_unlock','cheat_unlock','runtime_unlock','add_studs','add_bricks','noop','area_access')


def effect_identity(effect):
    plan=effect_plan(effect)
    return (plan['kind'],plan.get('native_name',plan.get('ability',plan.get('kind'))))


def primary_class_for_model(native_name):
    native_name=native_name.upper()
    if native_name=='ROBBER_REXFURY':return 'Robber'
    return next((name for name,model in CLASS_MODELS.items() if model==native_name),None)


def pool_candidates(items,allowed,experimental=False,progressive_astronaut=True):
    """Keep old IDs/effects for receipts, but emit one native class entitlement."""
    result=[]
    for name,row in items.items():
        category=row['category']
        if not allowed.get('ability' if category=='progressive' else category,False):continue
        effect=dict(row,name=name)
        if category=='area_pass':
            # Keep every old alias ID readable but only emit canonical passes.
            if not experimental or name!='Area Pass: '+row.get('native_name','') or row.get('native_name')=='SF_Docks':continue
        if not experimental and not supported_effect(effect):continue
        if category=='character' and allowed.get('ability') and row.get('native_name') in set(CLASS_MODELS.values()):
            continue
        if allowed.get('ability') and category=='character' and row.get('native_name')=='ROBBER_REXFURY':continue
        if progressive_astronaut and allowed.get('ability'):
            if name in ('Ability: Astronaut','Ability: Jetpack','Character: ASTRONAUT'):continue
        elif name==PROGRESSIVE_ASTRONAUT:continue
        result.append(name)
    return result


def has_capability(state,player,name):
    # Requirements describe actual named native capabilities, not arbitrary
    # world-region counters. Alias support keeps existing start inventories valid.
    if name in CLASS_MODELS:
        if state.has('Ability: '+name,player) or state.has('Character: '+CLASS_MODELS[name],player):return True
        if name=='Astronaut':return state.has(PROGRESSIVE_ASTRONAUT,player)
        if name=='Robber':return state.has('Ability: Rex Fury',player) or state.has('Character: ROBBER_REXFURY',player)
        return False
    if name=='Jetpack':
        legacy_class=state.has('Ability: Astronaut',player) or state.has('Character: ASTRONAUT',player)
        return state.has('Ability: Jetpack',player) or state.has(PROGRESSIVE_ASTRONAUT,player,2) or (
            legacy_class and state.has(PROGRESSIVE_ASTRONAUT,player))
    if name=='Color Gun':return state.has('Ability: Color Gun',player) or state.has('Ability: EnergyGun',player)
    if name=='Detective Scan':return state.has('Ability: Detective Scan',player)
    if name=='Rex Fury':return state.has('Ability: Rex Fury',player) or state.has('Character: ROBBER_REXFURY',player)
    return state.has('Ability: '+name,player)


def class_for_skin(effect,roster):
    if effect.get('category')!='character':return None
    native=effect.get('native_name','').upper()
    if primary_class_for_model(native):return None
    entry=roster.get('entries',{}).get(native,{})
    if entry.get('kind')!='character':return None
    categories=[category for category in entry.get('categories',[]) if category in CLASS_CATEGORIES]
    return CLASS_CATEGORIES[categories[0]] if len(categories)==1 else None


def entitled_classes(effects):
    classes=set()
    for effect in effects:
        plan=effect_plan(effect)
        if plan['kind']=='model_unlock':
            name=primary_class_for_model(plan['native_name'])
            if name:classes.add(name)
    return classes
