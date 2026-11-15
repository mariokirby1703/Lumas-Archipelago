"""Reproducible Source_Key merge and coverage export; never edit the Google Sheet."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
from collections import Counter

WORLD=Path(__file__).resolve().parents[1];ROOT=WORLD.parents[1]


def write_csv(path,rows,columns):
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(rows)


def main():
    output=WORLD/'docs/research/reliability';output.mkdir(parents=True,exist_ok=True)
    catalogue=json.loads((WORLD/'catalogue.json').read_text())
    baseline=json.loads(subprocess.check_output(['git','show','e9247703c:worlds/lego_city_undercover/catalogue.json'],cwd=ROOT))
    for group in ('locations','items'):
        for key,row in baseline[group].items():
            if catalogue[group].get(key,{}).get('id')!=row['id']:raise ValueError('Changed legacy ID: '+key)
    raw=json.loads((WORLD/'notes/analysis/pickup_catalogue.json').read_text())
    bindings=json.loads((WORLD/'bridge/city_pickup_bindings.json').read_text())
    before=json.loads(subprocess.check_output(['git','show','e9247703c:worlds/lego_city_undercover/bridge/city_pickup_bindings.json'],cwd=ROOT))
    by_source={r['source_key']:(bit,r) for bit,r in bindings.items()}
    areas=json.loads((WORLD/'bridge/area_names.json').read_text());area_case={k.casefold():v for k,v in areas.items()}
    sources=json.loads((WORLD/'bridge/city_pickup_sources.json').read_text());signatures=Counter(
        (r['tile_name'].casefold().removesuffix('_tech'),r['name'],r.get('native_type')) for r in sources)
    rows=[];extras=[]
    for row in raw:
        if row['type_code'] not in (80,106):continue
        key='source_pickup:'+row['source_key'];location=catalogue['locations'].get(key)
        resource=row['resource'];city='/levels/lego_city/lego_city/' in resource
        playable=(city or '/levels/standalones/' in resource) and 'gamemechanicstestarea' not in resource
        if playable and not location:raise ValueError('Missing playable source key: '+key)
        native_type={80:12,106:29}[row['type_code']]
        bit,proof=by_source.get(row['source_key'],('',{}))
        tile=Path(resource).stem.casefold().removesuffix('_tech')
        district=(location or {}).get('district') or ''
        data=dict(source_key=row['source_key'],ap_key=key,ap_id=(location or {}).get('id',''),
            area=area_case.get(district.casefold(),district),native_district=district,
            scope='city' if city else 'mission_hq' if playable else 'template_test_additional',
            source_type=row['type_code'],native_type=native_type,size='2x2' if row['type_code']==80 else '4x2',
            resource=resource,object_name=row['name'],x=row['resource_xyz'][0],y=row['resource_xyz'][1],z=row['resource_xyz'][2],
            coordinate_space='resource; parent transforms not proven',pickup_bit=bit,
            verification='native_binding_verified' if bit!='' else 'static_source_only',
            binding_evidence=proof.get('evidence',''),
            automatic_identity_eligible=signatures[(tile,row['name'],native_type)]==1,
            issue='' if bit!='' else 'runtime bit not observed' if playable else 'not a standard AP location')
        (rows if playable else extras).append(data)
    assert len(rows)==512 and len(extras)==38
    rows.sort(key=lambda r:(r['scope'],r['area'],r['source_key']));extras.sort(key=lambda r:r['source_key'])
    columns=list(rows[0])
    write_csv(output/'superbrick_sources_512.csv',rows,columns)
    write_csv(output/'template_test_sources_38.csv',extras,columns)
    write_csv(output/'unresolved_pickup_sources.csv',[r for r in rows if r['scope']=='city' and r['pickup_bit']==''],columns)
    new=[r for r in rows if r['pickup_bit']!='' and str(r['pickup_bit']) not in before]
    write_csv(output/'newly_verified_pickups.csv',new,columns)
    # This is a non-destructive review for the human Sheet, keyed by Source_Key.
    write_csv(output/'sheet_superbrick_merge_review.csv',rows,columns)
    summary=dict(baseline='e9247703c',legacy_ids_changed=0,playable_sources=len(rows),additional_sources=len(extras),
        packaged_bindings_before=len(before),packaged_bindings_after=len(bindings),new_packaged_bindings=len(new),
        unresolved_city_sources=sum(r['scope']=='city' and r['pickup_bit']=='' for r in rows),
        live_gameplay_tests_this_pass=0,game_running_during_probe=False,
        source_types=dict(Counter(str(r['source_type']) for r in rows)),
        sheet_rows=len(json.loads((WORLD/'bridge/location_design.json').read_text())['rows']),
        limitation='Structural registration proofs do not establish physics or a successful live pickup for every source')
    (output/'coverage.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
