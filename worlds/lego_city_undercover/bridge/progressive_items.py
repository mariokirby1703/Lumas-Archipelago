"""Deterministically resolve receipt-indexed progression; no game mutations here."""
try:
    from .item_delivery import effect_plan
except ImportError:
    from item_delivery import effect_plan

PROGRESSIVE_ASTRONAUT='Progressive Astronaut'
ASTRONAUT_STAGES=(dict(name='Ability: Astronaut',category='ability',classification='progression'),
                  dict(name='Ability: Jetpack',category='ability',classification='progression'))
def stages(base,tool):
    return tuple(dict(name='Ability: '+name,category='ability',classification='progression') for name in (base,tool))

PROGRESSIVE_FAMILIES={
    PROGRESSIVE_ASTRONAUT:ASTRONAUT_STAGES,
    'Progressive Robber':stages('Robber','Color Gun'),
    'Progressive Firefighter':stages('Firefighter','FireAxe'),
    'Progressive Police':stages('Police','GrappleGun'),
}
STAGE_LABELS={'Color Gun':'Color Gun','FireAxe':'Fire Axe','GrappleGun':'Grapple Gun'}


def managed_effects(effect):
    return list(PROGRESSIVE_FAMILIES.get(effect.get('name'),(effect,)))


def resolve_receipts(items,effect_table):
    """Order includes AP start inventory. Never use current RAM as stage input."""
    known=set();result=[]
    for index,item in enumerate(items):
        effect=effect_table.get(str(item.item))
        if effect is None:continue
        family=effect.get('name')
        if family in PROGRESSIVE_FAMILIES:
            stage=next((stage for stage in PROGRESSIVE_FAMILIES[family] if _identity(stage) not in known),None)
            if stage is None:
                effect=dict(name=family,category='progressive',effect='progressive_complete',
                            classification='useful',display_name=family+' (complete)')
            else:
                label=stage['name'].removeprefix('Ability: ')
                effect=dict(stage,display_name=family+': '+STAGE_LABELS.get(label,label))
        result.append((index,item,effect))
        known.add(_identity(effect))
    return result


def _identity(effect):
    plan=effect_plan(effect)
    return plan['kind'],plan.get('native_name',plan.get('ability'))
