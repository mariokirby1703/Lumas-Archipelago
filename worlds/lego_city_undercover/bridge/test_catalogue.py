"""All classified native outfits/vehicles, including non-progression test models."""
def test_catalogue(catalogue,roster):
    try:
        from .capabilities import RETIRED_POOL_ITEMS,ITEM_ALIASES
    except ImportError:
        from capabilities import RETIRED_POOL_ITEMS,ITEM_ALIASES
    effects={name:dict(row,name=name) for name,row in catalogue['items'].items() if name not in RETIRED_POOL_ITEMS and name not in ITEM_ALIASES}
    for native,row in roster['entries'].items():
        if row['kind'] not in ('character','vehicle'):continue
        prefix='Character' if row['kind']=='character' else 'Vehicle'
        name=prefix+': '+native
        effects.setdefault(name,dict(name=name,category=row['kind'],native_name=native,test_only=True))
    return effects


def normalize_search(text):
    text=text.casefold().replace('_',' ').replace(':',' ').replace('-',' ')
    if text.strip() in ('scanner','ability  scanner','kriminellenscan','personenscan'):
        return 'criminal scan'
    return text


def item_states(effects,snapshot,models,data=None,runtime=None):
    from item_delivery import effect_plan
    from native_save import model_save_flags,cheat_save_flags,ability_saved
    inventory={r['model_id']:r for r in snapshot.get('characters',[])}
    cheats={r['native_name']:r for r in snapshot.get('cheats',{}).get('records',[])}
    result={}
    for name,effect in effects.items():
        plan=effect_plan(effect);kind=plan['kind'];state=dict(owned=None,saved=None,found=None,pending=None,active=None,index=None)
        if kind=='model_unlock' and plan['native_name'] in models:
            index=models[plan['native_name']];row=inventory.get(index,{})
            state.update(index=index,owned=bool(row.get('owned_byte')),found=bool(row.get('found_bit')),pending=bool(row.get('pending_grant')))
            if data is not None:
                flags=model_save_flags(data,index);state.update(saved=flags['owned'],saved_found=flags['found'])
        elif kind=='runtime_unlock':
            state.update(owned=(runtime or {}).get(plan['ability']),persistence='AP receipt journal',index=0)
        elif kind=='cheat_unlock' and plan.get('native_name') in cheats:
            row=cheats[plan['native_name']];state.update(index=row['index'],owned=row['effect_flag'],found=row.get('found'),active=row.get('active'))
            if data is not None:
                flags=cheat_save_flags(data,row['index']);state.update(saved=flags['owned'],saved_found=flags['found'])
        elif kind=='ability_unlock' and plan['ability'] in snapshot.get('ability_raw',{}):
            row=snapshot['ability_raw'][plan['ability']];state.update(owned=bool(row['existing']),pending=bool(row.get('pending')))
            if data is not None:
                try:state['saved']=ability_saved(data,plan['ability'])
                except ValueError:pass
        result[name]=state
    return result
