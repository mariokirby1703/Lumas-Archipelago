"""Deterministically resolve receipt-indexed progression; no game mutations here."""
try:
    from .item_delivery import effect_plan
except ImportError:
    from item_delivery import effect_plan

PROGRESSIVE_ASTRONAUT='Progressive Astronaut'
ASTRONAUT_STAGES=(dict(name='Ability: Astronaut',category='ability',classification='progression'),
                  dict(name='Ability: Jetpack',category='ability',classification='progression'))


def managed_effects(effect):
    return list(ASTRONAUT_STAGES) if effect.get('name')==PROGRESSIVE_ASTRONAUT else [effect]


def resolve_receipts(items,effect_table):
    """Order includes AP start inventory. Never use current RAM as stage input."""
    known=set();result=[]
    for index,item in enumerate(items):
        effect=effect_table.get(str(item.item))
        if effect is None:continue
        if effect.get('name')==PROGRESSIVE_ASTRONAUT:
            stage=next((stage for stage in ASTRONAUT_STAGES if _identity(stage) not in known),None)
            if stage is None:
                effect=dict(name=PROGRESSIVE_ASTRONAUT,category='progressive',effect='progressive_complete',
                            classification='useful',display_name='Progressive Astronaut (complete)')
            else:
                effect=dict(stage,display_name=f'Progressive Astronaut: {stage["name"].removeprefix("Ability: ")}')
        result.append((index,item,effect))
        known.add(_identity(effect))
    return result


def _identity(effect):
    plan=effect_plan(effect)
    return plan['kind'],plan.get('native_name',plan.get('ability'))
