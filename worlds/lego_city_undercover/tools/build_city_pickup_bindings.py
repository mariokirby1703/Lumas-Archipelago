"""Reproduce writer-derived static city mappings; isolate collisions explicitly."""
import collections
import csv
import json
from pathlib import Path
import re

WORLD=Path(__file__).resolve().parents[1]


def main():
    analysis=WORLD/'notes/analysis'
    groups=collections.defaultdict(list)
    for row in json.loads((analysis/'pickup_catalogue.json').read_text()):
        if '/levels/lego_city/lego_city/' in row['resource'] and row['type_code'] in (80,106):
            groups[row['resource']].append(row)
    native=json.loads((analysis/'live_all_native_pickup_bindings.json').read_text())
    observed={(r['collection_bit'],r['name']) for r in native['objects'] if r['collection_bit'] is not None}
    rows=[]
    for resource,objects in groups.items():
        match=re.search(r'_(\d{2})(\d{2})(?:_tech)?\.giz$',resource)
        if not match:continue
        x,y=map(int,match.groups())
        for index,obj in enumerate(objects):
            bit=(y*38+x)*8+index
            rows.append(dict(bit=bit,source_key=obj['source_key'],resource=resource,name=obj['name'],
                             position=obj['resource_xyz'],local_index=index,tile_xy=[x,y],
                             evidence='live_instance_match' if (bit,obj['name']) in observed else 'static_rank_candidate',
                             status='out_of_range' if index>=8 else 'candidate'))
    counts=collections.Counter(r['bit'] for r in rows)
    for r in rows:
        if counts[r['bit']]>1:r['status']='collision'
    # Production mapping deliberately only includes identities observed in live instances.
    verified={str(r['bit']):r for r in rows if r['status']=='candidate' and r['evidence']=='live_instance_match'}
    (WORLD/'bridge/city_pickup_bindings.json').write_text(json.dumps(verified,indent=2),encoding='utf-8')
    (analysis/'city_pickup_binding_candidates.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    sources=[
        dict(source_key=r['source_key'],name=r['name'],
             tile_name=Path(r['resource']).stem.removesuffix('_tech').lower()) for r in rows
    ]
    for obj in json.loads((analysis/'pickup_catalogue.json').read_text()):
        if (('/levels/standalones/' in obj['resource'] and obj['type_code'] in (80,106))
                or obj['type_code']==114):
            sources.append(dict(source_key=obj['source_key'],name=obj['name'],
                tile_name=Path(obj['resource']).stem.lower().removesuffix('_tech'),
                native_type={80:12,106:29,114:7}[obj['type_code']]))
    for reward in json.loads((WORLD/'bridge/activity_rewards.json').read_text()):
        sources.append(dict(source_key=reward['source_key'],name=reward['pickup_name'],
                            tile_name=reward['scene'].lower(),native_type=reward['native_type']))
    (WORLD/'bridge/city_pickup_sources.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
    with (analysis/'city_pickup_binding_candidates.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['bit','source_key','name','x','y','z','index','status','evidence'])
        for r in rows:writer.writerow([r['bit'],r['source_key'],r['name'],*r['position'],r['local_index'],r['status'],r['evidence']])
    print(f'{len(rows)} source candidates; {len(verified)} live-instance matches; {sum(n>1 for n in counts.values())} colliding bit IDs')


if __name__=='__main__':main()
