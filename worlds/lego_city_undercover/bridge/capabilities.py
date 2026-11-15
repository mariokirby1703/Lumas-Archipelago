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
try:
    from .progressive_items import PROGRESSIVE_FAMILIES
except ImportError:
    from progressive_items import PROGRESSIVE_FAMILIES

PROGRESSIVE_ASTRONAUT='Progressive Astronaut'
ITEM_ALIASES={'Ability: Scanner':'Ability: Criminal Scan'}
RETIRED_POOL_ITEMS=frozenset(('Ability: Surveillance','Ability: Carry Objects','Ability: Climbing'))
UNSUPPORTED_ABILITIES=frozenset(('Carry Objects','Climbing','Crowbar','Fishing','Stethoscope'))
NATIVE_TOOL_NAMES=frozenset(ABILITY_NAMES)
CLASS_CATEGORIES={1:'Police',2:'Robber',3:'Miner',4:'Astronaut',5:'Farmer',6:'Firefighter',7:'Construction Worker'}


def supported_effect(effect):
    if effect.get('name') in PROGRESSIVE_FAMILIES:return True
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


def pool_candidates(items,allowed,experimental=False,progressive_astronaut=True,progressive_options=None):
    """Keep old IDs/effects for receipts, but emit one native class entitlement."""
    result=[]
    enabled={'Progressive Astronaut':progressive_astronaut,'Progressive Robber':True,'Progressive Firefighter':True,'Progressive Police':True}
    if progressive_options is not None:enabled.update(progressive_options)
    identities={effect_identity(stage) for family in PROGRESSIVE_FAMILIES if enabled[family] for stage in PROGRESSIVE_FAMILIES[family]}
    for name,row in items.items():
        if name in RETIRED_POOL_ITEMS or name in ITEM_ALIASES:continue
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
        if name in PROGRESSIVE_FAMILIES:
            if not enabled[name]:continue
        elif allowed.get('ability') and effect_identity(effect) in identities:continue
        result.append(name)
    return result


def has_capability(state,player,name):
    # Requirements describe actual named native capabilities, not arbitrary
    # world-region counters. Alias support keeps existing start inventories valid.
    if name in CLASS_MODELS:
        if state.has('Ability: '+name,player) or state.has('Character: '+CLASS_MODELS[name],player):return True
        family='Progressive '+name
        if family in PROGRESSIVE_FAMILIES and state.has(family,player):return True
        if name=='Robber':return state.has('Ability: Rex Fury',player) or state.has('Character: ROBBER_REXFURY',player)
        return False
    tools={'Jetpack':('Astronaut','Progressive Astronaut'),'Color Gun':('Robber','Progressive Robber'),
           'EnergyGun':('Robber','Progressive Robber'),'FireAxe':('Firefighter','Progressive Firefighter'),
           'GrappleGun':('Police','Progressive Police')}
    if name in tools:
        base,family=tools[name]
        exact_base=state.has('Ability: '+base,player) or state.has('Character: '+CLASS_MODELS[base],player)
        legacy=state.has('Ability: '+name,player)
        if name in ('Color Gun','EnergyGun'):legacy=state.has('Ability: Color Gun',player) or state.has('Ability: EnergyGun',player)
        return has_capability(state,player,base) and (legacy or state.has(family,player,2) or (exact_base and state.has(family,player)))
    if name in ('Scanner','Criminal Scan'):
        return has_capability(state,player,'Police') and (state.has('Ability: Criminal Scan',player) or state.has('Ability: Scanner',player))
    if name in ('Detective Scan','Wiretap','Surveillance'):
        return has_capability(state,player,'Police') and state.has('Ability: '+name,player)
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
