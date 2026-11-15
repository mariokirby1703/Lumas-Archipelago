"""Import the user's read-only Sheet snapshot; keep design and native proof separate."""
import csv
import json
from pathlib import Path
import re
import hashlib

WORLD=Path(__file__).resolve().parents[1]
ROOT=WORLD.parents[1]
SNAPSHOT=ROOT/'build/lego_city_undercover/next_pass'


def native_rewards(catalogue,scripted=()):
    result={}
    for row in catalogue['locations'].values():
        d=row.get('activity_metadata') or {}
        if d.get('Reward')=='TokenAndGoldBrick' and d.get('RewardID'):
            result.setdefault(d['RewardID'].upper(),[]).append('objective:'+d['Name'])
    for row in scripted:result.setdefault(row['model'],[]).append(row['objective'])
    return result


def vehicle_theft_rewards(text):
    required=('SuperCounterUIAndAnim(#VehicleTheft, nTotal, nMax, false, tAward, nPlayer);','CityObjective_SetComplete( tDataNode );')
    if not all(marker in text for marker in required):raise ValueError('Unknown native vehicle-theft reward path')
    pairs=re.findall(r'tDataNode\s*=\s*"([^"]+)";(?:(?!tDataNode).)*?tAward\s*=\s*"([^"]+)";',text,re.S)
    if len(pairs)!=13:raise ValueError('Expected 13 native theft branches')
    return [dict(objective='objective:'+objective,model=model.upper(),classification='activity_reward',
                 evidence='same tDataNode completion and SuperCounterUIAndAnim tAward in native vehicle_thefts.sf') for objective,model in pairs]


def name_hint(text):
    text=re.sub(r'\([^)]*\)','',text)
    return ''.join(c for c in text.casefold() if c.isalnum())


def main():
    catalogue=json.loads((WORLD/'catalogue.json').read_text(encoding='utf-8'))
    rows=json.loads((SNAPSHOT/'locations.json').read_text(encoding='utf-8'))['values']
    records=[];by_key={}
    for index,raw in enumerate(rows[1:],2):
        row=(raw+['']*21)[:21];key=str(row[13]).strip()
        # Never turn a row number or a fuzzy name into a native identity.
        record=dict(sheet_row=index,number=row[0],category=row[1],display_area=row[2],display_name=row[3],
                    design=dict(classes=row[4],abilities=row[5],auras=row[6],building_bricks=row[7],notes=row[8],
                                evidence='unverified_user_design; internet guide inputs; not native access proof'),
                    native_key=key or None,source_status=row[15],source_reference=row[17],technical_notes=row[20],
                    native_match='exact_key' if key in catalogue['locations'] else 'unmatched')
        records.append(record)
        if key in catalogue['locations']:by_key.setdefault(key,[]).append(record)
    source=WORLD/'notes/extracted/GAME4/jobs/scripts/city_setup/vehicle_thefts/vehicle_thefts.sf'
    scripted=vehicle_theft_rewards(source.read_text())
    for reward in scripted:
        if reward['objective'] not in catalogue['locations']:raise ValueError('Native theft objective missing: '+reward['objective'])
        reward['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    (WORLD/'bridge/scripted_activity_rewards.json').write_text(json.dumps(scripted,indent=2),encoding='utf-8')
    rewards=native_rewards(catalogue,scripted);relationships={}
    for key,row in catalogue['locations'].items():
        if row['category'] not in ('character_tokens','vehicle_tokens'):continue
        runtime=row.get('runtime') or {};model=runtime.get('native_name')
        matches=rewards.get(str(model).upper(),[])
        # The detector is the SAME global found bit that the automatic native
        # reward sets. It cannot establish a second independent collection.
        relationships[key]=dict(classification='ambiguous' if matches else 'unverified_source',
            automatic_reward_sources=matches,exclude_from_new_generation=bool(matches),
            reason='Global model-found detector also set by an automatic native activity reward; no independent pickup-bit detector' if matches else
                   'A model found flag alone does not prove a separately collectible token',
            independent_source_binding=runtime.get('kind')=='pickup')
        if runtime.get('kind')=='pickup':
            relationships[key].update(classification='independent_post_activity_pickup' if matches else 'independent_pickup',
                                      exclude_from_new_generation=False)
        if row.get('linked_story_reward')=='COP':
            relationships[key].update(classification='story_reward',exclude_from_new_generation=True,
                automatic_reward_sources=['story_disguise:COP'],
                reason='Native collection default links Grace to the same original COP wardrobe activation; no separate player interaction')
    design=dict(version=1,spreadsheet_id='1dt-6qi7bvCcV1975xHqtpiqgebrzzFjBk9wXfGIvn3I',
                imported='2026-11-15',requirements_verified=False,rows=records)
    (WORLD/'bridge/location_design.json').write_text(json.dumps(design,indent=2,ensure_ascii=False),encoding='utf-8')
    (WORLD/'bridge/token_relationships.json').write_text(json.dumps(relationships,indent=2,sort_keys=True),encoding='utf-8')
    areas=json.loads((SNAPSHOT/'areas.json').read_text(encoding='utf-8'))['values']
    (WORLD/'bridge/area_names.json').write_text(json.dumps({r[0]:r[1] for r in areas[1:] if len(r)>1},indent=2),encoding='utf-8')
    out=WORLD/'docs/research'
    with (out/'sheet_location_review.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['sheet_row','number','display_name','area','native_key','native_match','requirement_evidence'])
        writer.writerows([r['sheet_row'],r['number'],r['display_name'],r['display_area'],r['native_key'],r['native_match'],r['design']['evidence']] for r in records)
    with (out/'token_reward_review.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['key','classification','exclude_new_seeds','automatic_reward_sources','reason'])
        writer.writerows([k,r['classification'],r['exclude_from_new_generation'],';'.join(r['automatic_reward_sources']),r['reason']] for k,r in relationships.items())
    excluded=json.loads((SNAPSHOT/'excluded_tokens.json').read_text(encoding='utf-8'))['values']
    # Preserve all 104 reviewed guide entries without fabricating native model mappings.
    (out/'sheet_excluded_token_evidence.json').write_text(json.dumps(dict(columns=excluded[0],rows=excluded[1:],
        native_mapping_status='guide display names are not treated as native model IDs'),indent=2,ensure_ascii=False),encoding='utf-8')
    roster=json.loads((WORLD/'bridge/collection_manifest.json').read_text())['entries'];hints={}
    for model in roster:
        suffix=re.sub(r'^(?:COLLECT_\d+-\d+_|COP_|ROBBER_|MINER_|ASTRONAUT_|FARMER_|FIREMAN_|CONSTRUCTION_|CIVILIAN_|NPC_)','',model)
        hints.setdefault(name_hint(suffix),[]).append(model)
        hints.setdefault(name_hint(model.split('_',1)[-1]),[]).append(model)
    with (out/'sheet_excluded_token_review.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['guide_token','guide_activity','native_name_candidates_NOT_PROOF','existing_source_keys','native_reward_witnesses','decision'])
        for raw in excluded[1:]:
            row=(raw+['']*8)[:8];models=sorted(set(hints.get(name_hint(row[0]),[])))
            keys=[key for key,record in catalogue['locations'].items() if (record.get('runtime') or {}).get('native_name') in models]
            witnesses=[key for model in models for key in rewards.get(model,[])]
            decision=('name_hint_unresolved' if len(models)!=1 else 'already_absent_as_global_found_check' if not keys else
                      'native_duplicate_retired_for_new_seeds' if any(relationships.get(key,{}).get('exclude_from_new_generation') for key in keys) else
                      'inspect_native_reward_relationship; display-name similarity never deletes a check')
            writer.writerow([row[0],row[4],';'.join(models),';'.join(keys),';'.join(witnesses),decision])
    print(f'{len(records)} design rows; {sum(r["native_match"]=="exact_key" for r in records)} exact keys; '
          f'{sum(r["exclude_from_new_generation"] for r in relationships.values())} overlapping found-flag detectors excluded')


if __name__=='__main__':main()
