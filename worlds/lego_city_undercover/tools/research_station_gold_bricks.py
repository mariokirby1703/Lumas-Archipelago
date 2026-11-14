"""Inventory all static station gold-brick sources; optionally register exact pickups."""
import argparse
import csv
import json
from pathlib import Path
import re

WORLD=Path(__file__).resolve().parents[1]
REMAINING={
    'GB_Donut':('donut','Police Station Briefing Room: Donut Task',['LCPD_BR_Donut'],'robber'),
    'GB_Portraits':('portraits','Police Station Lobby: Four Portraits',
                    [f'LCPD_Lobby_Portrait{i:02}' for i in range(1,5)],None),
    'GB_FilingCabinet':('silver_filing_cabinet','Police Station Lobby: Silver Filing Cabinet',['LCPD_Lobby_Dynamite'],'miner'),
    'GB_GoldBrickShop':('gold_brick_shop','Police Station Basement: Gold Brick Shop Hidden Brick',['LCPD_BM_GB_GBShop'],'construction'),
    'GB_RedBrickShop':('red_brick_shop','Police Station Basement: Red Brick Shop Hidden Brick',['LCPD_BM_GB_RBShop'],'robber'),
    'GB_VehShop':('vehicle_shop','Police Station Basement: Vehicle Shop Hidden Brick',['LCPD_BM_GB_VehShop'],'Parkour'),
    'GB_FireDoor':('fire_door','Police Station Basement: Fire Door',['LCPD_BM_GB_FireDoor'],'fireman'),
}


def research(register=False):
    pickups=json.loads((WORLD/'notes/analysis/pickup_catalogue.json').read_text())
    sources=[r for r in pickups if '/police_station/' in r['resource'] and r['type_code']==71]
    scanner=(WORLD/'notes/extracted/GAME7/stuff/scanner/scanner_objectives.txt').read_text()
    objectives={}
    for block in re.findall(r'info_start(.*?)info_end',scanner,re.S):
        fields=dict(re.findall(r'(instanceName|lockType|lockName)\s+"([^"]+)"',block))
        if fields.get('instanceName','').startswith('LCPD_'):objectives[fields['instanceName']]=fields
    path=WORLD/'bridge/activity_rewards.json';rewards=json.loads(path.read_text())
    records=[]
    for source in sources:
        name=source['name'];known=next((r for r in rewards if r['source_key']==source['source_key']),None)
        if name in REMAINING:
            suffix,label,clues,requirement=REMAINING[name]
            locks=[objectives[clue] for clue in clues if clue in objectives and 'lockName' in objectives[clue]]
            if requirement and not any(lock['lockName']==requirement for lock in locks):
                raise ValueError('Scanner requirement mismatch: '+name)
            if not known:
                scene=Path(source['resource']).stem
                known=dict(key=scene+':'+suffix,name=label,source_key=source['source_key'],scene=scene,
                    pickup_name=name,native_type=11,static_type=71,district=None,coordinates=source['resource_xyz'],
                    category='city_activities',prerequisite_objectives=clues,status='static_activity_reward',
                    scanner_locks=locks,evidence='Unique static type-71 station reward; exact scene/name reader; collection not yet live tested')
                if register:rewards.append(known)
        records.append(dict(pickup=name,source_key=source['source_key'],coordinates=source['resource_xyz'],
            name=known['name'] if known else None,scanner_locks=(known or {}).get('scanner_locks',[]),
            live_verified=(known or {}).get('status','verified_activity_reward')=='verified_activity_reward',
            status=(known or {}).get('status','verified_activity_reward')))
    out=WORLD/'notes/analysis/police_station_gold_bricks';out.mkdir(exist_ok=True)
    (out/'catalogue.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    with (out/'locations.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(('pickup','name','source_key','x','y','z','scanner_locks','status'))
        for r in records:writer.writerow((r['pickup'],r['name'],r['source_key'],*r['coordinates'],json.dumps(r['scanner_locks']),r['status']))
    if register:
        path.write_text(json.dumps(rewards,indent=2),encoding='utf-8')
        path=WORLD/'catalogue.json';catalogue=json.loads(path.read_text())
        for reward in rewards:
            key='source_pickup:'+reward['source_key'];old=catalogue['locations'][key]
            old.update(name=reward['name'],category=reward['category'],coordinates=reward['coordinates'],
                       coordinate_space='resource; transforms may apply',native_type='Activity reward',
                       runtime=dict(kind='activity_reward',reward_key=reward['key']),
                       status=reward.get('status','verified_activity_reward'),evidence=reward['evidence'])
            if reward.get('scanner_locks'):old['scanner_locks']=reward['scanner_locks']
            for clue in reward.get('prerequisite_objectives',[]):catalogue['locations'].pop('objective:'+clue,None)
        path.write_text(json.dumps(catalogue,indent=2,sort_keys=True),encoding='utf-8')
    print(len(sources),'station gold-brick sources;',len(REMAINING),'additional static bindings; no game writes')
    return records


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--register',action='store_true')
    research(parser.parse_args().register)
