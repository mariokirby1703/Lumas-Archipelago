"""Explicit player-YAML migration; slot data and journals never change seeds."""
from copy import deepcopy


REMOVED = ('wisp_unlocks','world_unlocks','chaos_emerald_items','red_ring_bundle_strategy')
GOALS = {'final_boss':'nega_wisp_armor','all_story_clears':'all_bosses','all_game_land':'all_game_land_stages','all_game_land_clears':'all_game_land_stages'}


def migrate_yaml(document):
    result=deepcopy(document)
    options=result.get('Sonic Colours (Wii)')
    if not isinstance(options,dict):raise ValueError('YAML does not contain Sonic Colours (Wii) options')
    changes=[]
    for name in REMOVED:
        if name in options:
            options.pop(name);changes.append(f'Removed {name}; progression is automatic and always enabled.')
    if 'wisp_capsule_sanity' in options:
        value=options.pop('wisp_capsule_sanity')
        if isinstance(value,dict):
            options['wisp_capsules']={'true':sum(weight for mode,weight in value.items() if mode not in ('off',0,False)),
                                      'false':sum(weight for mode,weight in value.items() if mode in ('off',0,False))}
        else:options['wisp_capsules']=value not in ('off',0,False)
        changes.append('Replaced Wisp Capsule Sanity with Wisp Capsules (all eligible instances).')
    goal=options.get('goal')
    if isinstance(goal,dict):options['goal']={GOALS.get(k,k):v for k,v in goal.items()}
    elif goal in GOALS:
        options['goal']=GOALS[goal];changes.append(f'Goal {goal} migrated to {options["goal"]}.')
    for key in ('start_inventory','start_inventory_from_pool','start_hints','local_items','non_local_items'):
        value=options.get(key)
        colours=('Green','Red','Blue','Yellow','Purple','Cyan','White')
        names={f'Chaos Emerald {i+1}':f'{c} Chaos Emerald' for i,c in enumerate(colours)}
        if isinstance(value,dict):options[key]={names.get(k,k):v for k,v in value.items()}
        elif isinstance(value,list):options[key]=[names.get(k,k) for k in value]
    return result,changes
