"""Build factual, deterministic experimental AP metadata from local research.

No raw game scripts/assets are packaged. Coordinates retain resource space.
Missing coordinates and unverified runtime bindings remain explicit nulls.
"""
import csv
import hashlib
import json
from pathlib import Path

WORLD = Path(__file__).resolve().parents[1]


def ident(key, base):
    return base + int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], 'little') % 900_000_000


def main():
    analysis = WORLD / 'notes/analysis'
    labels = json.loads((WORLD/'bridge/monitor_labels.json').read_text())
    roster = json.loads((WORLD/'bridge/collection_manifest.json').read_text())
    objectives = json.loads((analysis/'candidate_objectives.json').read_text())
    missions = json.loads((analysis/'candidate_missions.json').read_text())
    pickups = json.loads((analysis/'pickup_catalogue.json').read_text())
    bindings_file=WORLD/'bridge/city_pickup_bindings.json'
    bindings=json.loads(bindings_file.read_text()) if bindings_file.exists() else {}
    source_bits={r['source_key']:int(bit) for bit,r in bindings.items()}
    locations = {}
    for source in objectives:
        d = source['definition']; name = d['instanceName']; kind = d['objectiveTypeId']
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
        locations[key]=dict(name=f"{kind}: {p['source_key']}",category=category,district=district,
                            coordinates=p['resource_xyz'],coordinate_space='resource; transforms may apply',
                            source=resource,native_type=kind,source_index=p['index'],runtime=None,
                            status='static_candidate_unbound')
        if p['source_key'] in source_bits:
            locations[key].update(runtime=dict(kind='pickup',bit=source_bits[p['source_key']]),status='native_pickup')
    # Per-mission categories are synthetic completion candidates, not native IDs.
    levels=sorted({p['resource'].split('/levels/standalones/')[1].split('/')[0] for p in pickups
                   if '/levels/standalones/' in p['resource'] and 'gamemechanicstestarea' not in p['resource']})
    for level in levels:
        for category, suffixes in (('story_missions',['Complete']),('red_bricks',['Red Brick']),
                                   ('city_hero',['LEGO City Hero']),('shield_quarters',['TL','TR','BL','BR']),
                                   ('whole_shields',['Police Shield'])):
            for suffix in suffixes:
                key=f'mission:{level}:{suffix}'
                locations[key]=dict(name=f'{level}: {suffix}',category=category,district=None,coordinates=None,
                                    coordinate_space=None,source=level,runtime=None,status='synthetic_unbound')
    items={}
    for name,row in roster['entries'].items():
        if not row['counts_for_progress']:continue
        prefix='Character' if row['kind']=='character' else 'Vehicle'
        items[f'{prefix}: {name}']=dict(category=row['kind'],classification='filler',native_name=name)
    for tool in ('Police','Robber','Miner','Astronaut','Farmer','Firefighter','Construction Worker',
                 'Rex Fury','Stethoscope','Crowbar','GrappleGun','EnergyGun','Scanner','Surveillance',
                 'Wiretap','Jetpack','FireAxe','SuperBuild','Parkour','Fishing','Carry Objects','Climbing'):
        items[f'Ability: {tool}']=dict(category='ability',classification='useful')
    for level in levels:items[f'Story Access: {level}']=dict(category='story_access',classification='useful')
    for district in sorted({r['district'] for r in locations.values() if r['district']}):
        items[f'Area Pass: {district}']=dict(category='area_pass',classification='useful')
    items['Studs 1,000']=dict(category='filler',classification='filler')
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
