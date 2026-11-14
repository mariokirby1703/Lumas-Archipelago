"""Build factual, deterministic experimental AP metadata from local research.

No raw game scripts/assets are packaged. Coordinates retain resource space.
Missing coordinates and unverified runtime bindings remain explicit nulls.
"""
import csv
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

WORLD = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from red_bricks import redbrick_location_key
from activity_rewards import ACTIVITY_REWARDS


def ident(key, base):
    return base + int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], 'little') % 900_000_000


def main():
    analysis = WORLD / 'notes/analysis'
    labels = json.loads((WORLD/'bridge/monitor_labels.json').read_text())
    roster = json.loads((WORLD/'bridge/collection_manifest.json').read_text())
    objectives = json.loads((analysis/'candidate_objectives.json').read_text())
    missions = json.loads((analysis/'candidate_missions.json').read_text())
    pickups = json.loads((analysis/'pickup_catalogue.json').read_text())
    scenes={}
    for resource in (WORLD/'notes/extracted').rglob('*.giz'):
        path=resource.relative_to(WORLD/'notes/extracted').as_posix()
        if '/levels/standalones/' not in path:continue
        level=path.split('/levels/standalones/')[1].split('/')[0]
        scenes.setdefault(resource.stem.lower().removesuffix('_tech'),set()).add(level)
    for p in pickups:
        if '/levels/standalones/' not in p['resource']:continue
        level=p['resource'].split('/levels/standalones/')[1].split('/')[0]
        scenes.setdefault(Path(p['resource']).stem.lower().removesuffix('_tech'),set()).add(level)
    (WORLD/'bridge/mission_scene_names.json').write_text(json.dumps(
        {name:next(iter(levels)) for name,levels in sorted(scenes.items()) if len(levels)==1},indent=2),encoding='utf-8')
    bindings_file=WORLD/'bridge/city_pickup_bindings.json'
    bindings=json.loads(bindings_file.read_text()) if bindings_file.exists() else {}
    source_bits={r['source_key']:int(bit) for bit,r in bindings.items()}
    token_sources=[p for p in pickups if p['type_code']==122 and p['name'].upper() in roster['entries']]
    token_counts=Counter(p['name'].upper() for p in token_sources)
    locations = {}
    for source in objectives:
        d = source['definition']; name = d['instanceName']; kind = d['objectiveTypeId']
        if any(name in reward.get('prerequisite_objectives',[]) for reward in ACTIVITY_REWARDS):continue
        category = {'SuperBuild':'super_builds', 'SuperBuild_Level':'super_builds',
                    'DisguiseBooth':'disguise_booths', 'ROBBER_ATMSmash':'atms',
                    'TicketMachine':'train_stations', 'Clue':'unverified_clues'}.get(kind, 'city_activities')
        key = 'objective:'+name
        locations[key] = dict(name=f'{kind}: {name}', category=category, district=d.get('cityDistrict'),
                              coordinates=None, coordinate_space=None, source=name,
                              native_type=kind, source_requirements=d,
                              runtime=dict(kind='objective', name=name),
                              status='unverified_prerequisite' if kind=='Clue' else 'native_objective')
    for source in missions:
        d=source['definition']; name=d['Name']; key='objective:'+name
        if key not in locations:
            locations[key]=dict(name=f"Activity: {name}",category='city_activities',district=None,
                                coordinates=None,coordinate_space=None,source=name,source_requirements=d,
                                runtime=dict(kind='objective',name=name),status='static_candidate')
        locations[key]['activity_metadata']=d
    for p in pickups:
        resource=p['resource']
        if not ('/levels/lego_city/lego_city/' in resource or '/levels/standalones/' in resource):continue
        if 'gamemechanicstestarea' in resource:continue
        key='source_pickup:'+p['source_key']; kind=p.get('native_type_label',f"PickupType{p['type_code']}")
        district=resource.split('/levels/lego_city/lego_city/')[-1].split('/')[0] if '/levels/lego_city/lego_city/' in resource else None
        category='super_bricks' if p['type_code'] in (80,106) else 'unverified_pickups'
        if p['type_code']==114:
            # Story missions already have exactly one Red Brick location.
            if '/levels/standalones/' in resource:continue
            category='red_bricks';kind='Red Brick: '+p['name']
        locations[key]=dict(name=f"{kind}: {p['source_key']}",category=category,district=district,
                            coordinates=p['resource_xyz'],coordinate_space='resource; transforms may apply',
                            source=resource,native_type=kind,source_index=p['index'],runtime=None,
                            status='static_candidate_unbound')
        if p['source_key'] in source_bits:
            locations[key].update(runtime=dict(kind='pickup',bit=source_bits[p['source_key']]),status='native_pickup')
        native_name=p['name'].upper()
        if p['type_code']==122 and native_name in roster['entries']:
            entry=roster['entries'][native_name]
            if entry['counts_for_progress']:
                locations[key].update(name=f"{entry['kind'].title()} Token: {p['name']} ({p['source_key']})",
                    category=entry['kind']+'_tokens',
                    runtime=dict(kind='model_found',native_name=native_name) if token_counts[native_name]==1 else None,
                    status='experimental_model_found' if token_counts[native_name]==1 else 'ambiguous_model_source')
    # Primary story disguises are grants, not type-122 pickup source records.
    for default in roster['defaults']:
        if default['player']!=1 or default['class_name']=='generic':continue
        name=default['model'];key='story_disguise:'+name
        locations[key]=dict(name=f"Story Disguise: {default['class_name']} ({name})",
            category='character_tokens',district=None,coordinates=None,coordinate_space=None,
            source='primary class default; native pending/found model state',
            runtime=dict(kind='model_found',native_name=name),status='experimental_model_found')
    # Per-mission categories are synthetic completion candidates, not native IDs.
    levels=sorted({p['resource'].split('/levels/standalones/')[1].split('/')[0] for p in pickups
                   if '/levels/standalones/' in p['resource'] and 'gamemechanicstestarea' not in p['resource']})
    for level in levels:
        for category, suffixes in (('story_missions',['Complete']),('red_bricks',['Red Brick']),
                                   ('city_hero',['LEGO City Hero']),('shield_quarters',['TL','TR','BL','BR']),
                                   ('whole_shields',['Police Shield'])):
            for suffix in suffixes:
                if category=='red_bricks':continue
                key=f'mission:{level}:{suffix}'
                locations[key]=dict(name=f'{level}: {suffix}',category=category,district=None,coordinates=None,
                                    coordinate_space=None,source=level,runtime=None,status='synthetic_unbound')
    # Red Brick locations are backed by actual source records, never one synthetic
    # entry per resource (Police Station contains no Red Brick pickup).
    red_groups={}
    for pickup in pickups:
        if pickup['type_code']!=114:continue
        key=redbrick_location_key(pickup['source_key'])
        if key and key.startswith('mission:'):red_groups.setdefault(key,[]).append(pickup)
    for key,group in red_groups.items():
        mission=key.split(':')[1]
        locations[key]=dict(name=f'{mission}: Red Brick',category='red_bricks',district=None,
            coordinates=group[0]['resource_xyz'] if len(group)==1 else None,
            coordinate_space='resource; transforms may apply' if len(group)==1 else None,
            source=mission,source_pickups=[p['source_key'] for p in group],
            runtime=dict(kind='red_brick',mission=mission),status='experimental_red_brick')
    for reward in ACTIVITY_REWARDS:
        key='source_pickup:'+reward['source_key']
        locations[key]=dict(name=reward['name'],category=reward['category'],district=reward['district'],
            coordinates=reward['coordinates'],coordinate_space='resource; transforms may apply',
            source=reward['source_key'],native_type='Activity reward',
            runtime=dict(kind='activity_reward',reward_key=reward['key']),status='verified_activity_reward',
            evidence=reward['evidence'])
    items={}
    for name,row in roster['entries'].items():
        if not row['counts_for_progress']:continue
        prefix='Character' if row['kind']=='character' else 'Vehicle'
        primary={d['model'] for d in roster['defaults'] if d['player']==1 and d['class_name']!='generic'}
        items[f'{prefix}: {name}']=dict(category=row['kind'],classification='progression' if name in primary else 'useful' if row['kind']=='character' else 'filler',native_name=name)
    for tool in ('Police','Robber','Miner','Astronaut','Farmer','Firefighter','Construction Worker',
                 'Rex Fury','Stethoscope','Crowbar','GrappleGun','EnergyGun','Scanner','Surveillance',
                 'Wiretap','Jetpack','FireAxe','SuperBuild','Parkour','Fishing','Carry Objects','Climbing'):
        items[f'Ability: {tool}']=dict(category='ability',classification='progression')
    cheat_names={r['native_name'] for r in json.loads((WORLD/'bridge/cheat_manifest.json').read_text())}
    for name in sorted(cheat_names):
        if name.startswith('CHEAT_SCOREX'):continue
        items['Red Brick Cheat: '+name]=dict(category='cheat',classification='useful',native_name=name)
    for multiplier in (2,4,6,8,10):
        items[f'Red Brick Cheat: Studs x{multiplier}']=dict(category='cheat',classification='useful',
            effect='stud_multiplier',multiplier=multiplier,native_name=f'CHEAT_SCOREX{multiplier}')
    for level in levels:items[f'Story Access: {level}']=dict(category='story_access',classification='useful')
    for district in sorted({r['district'] for r in locations.values() if r['district']}):
        items[f'Area Pass: {district}']=dict(category='area_pass',classification='useful')
    items['Studs 1,000']=dict(category='filler',classification='filler')
    for amount in (1000,10000,100000):
        items[f'Studs {amount:,}']=dict(category='filler',classification='filler',effect='add_studs',amount=amount)
    for amount in (100,250,1000,10000):
        items[f'Super Bricks {amount:,}']=dict(category='building_bricks' if amount>=1000 else 'filler',
            classification='useful' if amount>=1000 else 'filler',effect='add_bricks',amount=amount)
    for k,r in locations.items():r['id']=ident(k,1_000_000_000)
    for k,r in items.items():r['id']=ident(k,2_000_000_000)
    for table in (locations,items):
        if len({r['id'] for r in table.values()})!=len(table):raise ValueError('ID collision')
    report=dict(version=1,locations=locations,items=items,levels=levels,
                runtime_bindings_are_partial=True,all_coordinates_are_world_space=False)
    (WORLD/'catalogue.json').write_text(json.dumps(report,indent=2,sort_keys=True),encoding='utf-8')
    with (analysis/'ap_item_catalogue.csv').open('w',newline='',encoding='utf-8') as f:
        wr=csv.writer(f);wr.writerow(['name','id','category','classification','native_name'])
        for name,r in items.items():wr.writerow([name,r['id'],r['category'],r['classification'],r.get('native_name')])
    with (analysis/'ap_location_catalogue.csv').open('w',newline='',encoding='utf-8') as f:
        wr=csv.writer(f);wr.writerow(['key','id','name','category','district','x','y','z','coordinate_space','status'])
        for k,r in locations.items():wr.writerow([k,r['id'],r['name'],r['category'],r['district'],*(r['coordinates'] or [None]*3),r['coordinate_space'],r['status']])
    print(f'{len(locations)} location candidates; {len(items)} items; {len(levels)} standalone resource groups')


if __name__=='__main__':main()
