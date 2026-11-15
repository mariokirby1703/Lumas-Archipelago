"""Receipt-to-effect planning. A plan is never an applied native grant."""
import json

CLASS_MODELS={'Police':'COP','Robber':'ROBBER','Miner':'MINER','Astronaut':'ASTRONAUT',
    'Farmer':'FARMER','Firefighter':'FIREMAN','Construction Worker':'CONSTRUCTION_LEGOCITYCONSTRUCTIONWORKER'}


def effect_plan(item):
    if item.get('effect')=='progressive_complete':return dict(kind='noop',reason='Progressive stages already entitled')
    category=item.get('category')
    if category=='area_pass' and item.get('effect')=='area_access':
        return dict(kind='area_access',district=item['native_name'])
    if item.get('effect') in ('add_studs','add_bricks'):
        amount=item.get('amount')
        if type(amount) is not int or not 0<amount<=100000:raise ValueError('Invalid currency amount')
        return dict(kind=item['effect'],amount=amount)
    if category in ('character','vehicle'):
        return dict(kind='model_unlock',native_name=item['native_name'].upper())
    if category=='ability':
        name=item['name'].removeprefix('Ability: ')
        if name=='Criminal Scan':return dict(kind='ability_unlock',ability='Scanner')
        if name=='Detective Scan':return dict(kind='runtime_unlock',ability='DetectiveScan')
        if name=='Color Gun':return dict(kind='ability_unlock',ability='EnergyGun')
        if name=='Rex Fury':return dict(kind='model_unlock',native_name='ROBBER_REXFURY')
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
