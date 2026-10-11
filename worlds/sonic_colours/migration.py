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
    for old in ('starting_act', 'level_randomization'):
        if old in options:
            options.pop(old)
            changes.append(f'Removed unsupported {old}; restored fixed vanilla introduction.')
    if 'egg_medal_sanity' in options:
        options['eggman_heart_sanity'] = options.pop('egg_medal_sanity')
        changes.append('Renamed Egg Medal Sanity to Eggman Heart Sanity.')
    if 'world_progression' not in options:
        options['world_progression'] = 'sequential'
        changes.append('Added sequential World Progression.')
    if 'music_randomization' in options:
        music = options['music_randomization']
        if isinstance(music, dict):
            off = sum(weight for key, weight in music.items()
                      if key in ('off', 'false', False, 0))
            on = sum(weight for key, weight in music.items()
                     if key not in ('off', 'false', False, 0))
            options['music_randomization'] = {'true': on, 'false': off}
        else:
            options['music_randomization'] = bool(music) and music not in ('off', 'false', False, 0)
        changes.append('Converted Music Randomization to On/Off.')
    else:
        options['music_randomization'] = True
        changes.append('Enabled Music Randomization by default.')
    for key in ('start_inventory','start_inventory_from_pool','start_hints','local_items','non_local_items'):
        value=options.get(key)
        colours=('Green','Red','Blue','Yellow','Purple','Cyan','White')
        names={f'Chaos Emerald {i+1}':f'{c} Chaos Emerald' for i,c in enumerate(colours)}
        names.update({'Red Ring (+1)':'Red Ring','Red Rings (+5)':'5 Red Rings','Red Rings (+10)':'10 Red Rings'})
        if isinstance(value,dict) and 'Terminal Velocity Access' in value:
            value={k:v for k,v in value.items() if k!='Terminal Velocity Access'}
            changes.append(f'Removed retired Terminal Velocity Access from {key}.')
        elif isinstance(value,list) and 'Terminal Velocity Access' in value:
            value=[k for k in value if k!='Terminal Velocity Access']
            changes.append(f'Removed retired Terminal Velocity Access from {key}.')
        if isinstance(value,dict):options[key]={names.get(k,k):v for k,v in value.items()}
        elif isinstance(value,list):options[key]=[names.get(k,k) for k in value]
    return result,changes
