"""Receipt-to-effect planning. A plan is never an applied native grant."""
import json

CLASS_MODELS={'Police':'COP','Robber':'ROBBER','Miner':'MINER','Astronaut':'ASTRONAUT',
    'Farmer':'FARMER','Firefighter':'FIREMAN','Construction Worker':'CONSTRUCTION_LEGOCITYCONSTRUCTIONWORKER'}


def effect_plan(item):
    category=item.get('category')
    if item.get('effect') in ('add_studs','add_bricks'):
        amount=item.get('amount')
        if type(amount) is not int or not 0<amount<=100000:raise ValueError('Invalid currency amount')
        return dict(kind=item['effect'],amount=amount)
    if category in ('character','vehicle'):
        return dict(kind='model_unlock',native_name=item['native_name'].upper())
    if category=='ability':
        name=item['name'].removeprefix('Ability: ')
        if name in CLASS_MODELS:return dict(kind='model_unlock',native_name=CLASS_MODELS[name])
        return dict(kind='ability_unlock',ability=name)
    if category=='cheat':return dict(kind='cheat_unlock',native_name=item.get('native_name'),
        multiplier=item.get('multiplier'),binding_verified=False)
    return dict(kind='unbound',reason='No verified native effect binding')


def entitlement_models(effects):
    return {plan['native_name'] for effect in effects
            if (plan:=effect_plan(effect))['kind']=='model_unlock'}


def register_delivery(journal,index,effect):
    plan=effect_plan(effect)
    journal.plan_delivery(index,plan)
    return plan
