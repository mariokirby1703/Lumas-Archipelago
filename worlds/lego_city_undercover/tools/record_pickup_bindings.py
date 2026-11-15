"""Verify loaded source/bit identities in two hash-gated read-only snapshots."""
import argparse
import json
from pathlib import Path
import sys

WORLD=Path(__file__).resolve().parents[1];ROOT=WORLD.parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from client_checks import KNOWN_AMBIGUOUS_PICKUP_BITS

HASH='624fed07274bbd105d1d571ecb97a290df6f6f0aff76898c516890da6d136f76'


def derive_bindings(snapshots,existing,catalogue):
    if len(snapshots)<2:raise ValueError('Two snapshots required')
    identity=[(s.get('process',{}).get('pid'),s.get('process',{}).get('sha256'),s.get('native_binding')) for s in snapshots]
    if any(i[1]!=HASH or i!=identity[0] for i in identity):raise ValueError('Snapshot process/save identity mismatch')
    candidates=[];conflicts=[];groups=[]
    for snapshot in snapshots:
        if snapshot.get('native_pickups',{}).get('status')!='read':raise ValueError('Pickup registry not read')
        group={}
        for row in snapshot['native_pickups'].get('objects',[]):
            bit=row.get('collection_bit')
            if bit is not None:group.setdefault(bit,[]).append(row)
        groups.append(group)
    for bit,rows in groups[0].items():
        all_rows=[group.get(bit,[]) for group in groups]
        if bit in KNOWN_AMBIGUOUS_PICKUP_BITS or any(len(r)!=1 for r in all_rows):
            conflicts.append(dict(bit=bit,reason='known or observed bit collision'));continue
        row=rows[0];source=row.get('source_key')
        if not source or any((r[0].get('source_key'),r[0].get('native_type'))!=(source,row.get('native_type')) for r in all_rows):continue
        location=catalogue['locations'].get('source_pickup:'+source)
        if not location or location['category']!='super_bricks':continue
        expected={'Gold Plate':12,'SuperBrick4X2':29}.get(location.get('native_type'))
        if row.get('status')!='native_writer_derived_binding' or expected!=row.get('native_type'):continue
        prior=existing.get(str(bit))
        if prior:
            if prior.get('source_key')!=source:conflicts.append(dict(bit=bit,reason='existing source differs',source=source))
            continue
        if any(r.get('source_key')==source for r in existing.values()):
            conflicts.append(dict(bit=bit,reason='source already has a different bit',source=source));continue
        candidates.append(dict(bit=bit,source_key=source,resource=location['source'],name=row['name'],
            position=row['position'],local_index=row['local_index'],tile_xy=row['tile_xy'],
            source_type=80 if expected==12 else 106,native_type=expected,
            status='native_writer_two_snapshot_identity',evidence='unique native tile/name/type + writer-derived packed bit; two stable hash-gated snapshots; no proximity heuristic'))
    duplicates={r['source_key'] for r in candidates if sum(c['source_key']==r['source_key'] for c in candidates)>1}
    conflicts.extend(dict(source=source,reason='same source observed at multiple native bits') for source in sorted(duplicates))
    return [r for r in candidates if r['source_key'] not in duplicates],conflicts


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--capture',action='store_true')
    parser.add_argument('--register',action='store_true');args=parser.parse_args()
    path=ROOT/'build/lego_city_undercover/next_pass/pickup_binding_snapshots.json'
    if args.capture:
        from live_monitor import Session
        session=Session()
        try:snapshots=[session.snapshot(),session.snapshot()]
        finally:session.close()
        path.write_text(json.dumps(snapshots,indent=2),encoding='utf-8')
    else:snapshots=json.loads(path.read_text(encoding='utf-8'))
    target=WORLD/'bridge/city_pickup_bindings.json';existing=json.loads(target.read_text())
    catalogue=json.loads((WORLD/'catalogue.json').read_text())
    added,conflicts=derive_bindings(snapshots,existing,catalogue)
    report=dict(writes_to_game=False,added=added,conflicts=conflicts,scope='native structural bindings; collection itself not live tested for every object')
    (WORLD/'docs/research/pickup_binding_pass_2026_11_15.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if args.register:
        existing.update({str(r['bit']):r for r in added});target.write_text(json.dumps(existing,indent=2),encoding='utf-8')
    print(f'{len(added)} new unique source/bit bindings; {len(conflicts)} conflicts; registered={args.register}')


if __name__=='__main__':main()
