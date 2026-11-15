"""Reproducible coverage audit and source-derived story preset graph (read only)."""
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

WORLD=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from capabilities import supported_effect
from source_logic import source_requirement
from location_design import enrich_catalogue


def write_csv(path,rows):
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    out=WORLD/'docs/research';out.mkdir(exist_ok=True)
    catalogue=json.loads((WORLD/'catalogue.json').read_text())
    enrich_catalogue(catalogue)
    locations=catalogue['locations'];items=catalogue['items']
    for field,rows in [('location',locations),('item',items)]:
        ids=[r['id'] for r in rows.values()]
        if len(ids)!=len(set(ids)):raise ValueError(f'Duplicate {field} IDs')
    coverage=[]
    for key,row in locations.items():
        runtime=row.get('runtime') or {}
        mission=key.startswith('mission:')
        coverage.append(dict(key=key,id=row['id'],name=row['name'],category=row['category'],district=row.get('district'),
            display_name=row.get('display_name'),display_area=row.get('display_area'),
            design_requirements=json.dumps(row.get('design_requirements'),ensure_ascii=False),
            token_relationship=json.dumps(row.get('token_relationship'),ensure_ascii=False),source_type_code=row.get('source_type_code'),
            superbrick_size=row.get('superbrick_size'),
            source_status=row['status'],detector='persistent_level_progress' if mission else runtime.get('kind','unbound'),
            requirement=source_requirement(row),coordinates_known=row.get('coordinates') is not None,
            coordinate_space=row.get('coordinate_space'),live_confirmed=row['status'] in ('verified_activity_reward','native_story_flag'),
            note='Collector parser supports this key; historical synthetic status is not live verification' if mission else ''))
    write_csv(out/'location_coverage.csv',coverage)
    identities={}
    for key,row in locations.items():
        if row.get('runtime'):
            identity=json.dumps(row['runtime'],sort_keys=True)
            identities.setdefault(identity,[]).append(key)
    duplicate_bindings=[dict(runtime=json.loads(identity),keys=keys) for identity,keys in identities.items() if len(keys)>1]
    (out/'duplicate_bindings.json').write_text(json.dumps(duplicate_bindings,indent=2),encoding='utf-8')
    effects=[dict(name=name,id=row['id'],category=row['category'],classification=row['classification'],
                  supported=supported_effect(dict(row,name=name))) for name,row in items.items()]
    write_csv(out/'item_effect_coverage.csv',effects)
    cheats=json.loads((WORLD/'bridge/cheat_manifest.json').read_text())
    write_csv(out/'cheat_matrix.csv',[dict(index=c['index'],native_name=c['native_name'],
        item=next((n for n,r in items.items() if r.get('native_name')==c['native_name']),None),
        source_discovery=f'profile+0xfa70 bit {c["index"]}',ownership=f'profile+0xfa80 bit {c["index"]}',
        active_state=f'cheat_table[{c["index"]}]+0x1a',grant='ownership only; native index/name/pointer guards',
        removal='owned bit + activation clearing through reviewed native test path',
        persistence='native autosave followed by exact serialized ownership-bit readback',
        native_test='synthetic ownership/save coverage',live_effect='not independently verified per cheat',
        activation='user toggles Extras; receipt does not force effect on') for c in cheats])
    # Preserve native variable names and provenance. Debug presets are observations,
    # not a safe list of flags to set on a real save.
    source=WORLD/'notes/extracted/GAME4/jobs/gotoflow.txt'
    raw=source.read_text(encoding='utf-8-sig');presets=[]
    for index,match in enumerate(re.finditer(r'PresetStart(.*?)PresetEnd',raw,re.S)):
        body=match[1]
        quoted=lambda key:re.findall(r'\b'+key+r'\s+"([^"]*)"',body)
        values=[dict(variable=m[1],job=m[2],value=m[3]) for m in re.finditer(r'j\(([^@=]+)@([^=]+)=([^\)]+)\)',body)]
        presets.append(dict(id=index,name=next(iter(quoted('name')),None),level=next(iter(quoted('level')),None),
                            door=next(iter(quoted('door')),None),variables=values))
    transitions=[]
    root=WORLD/'notes/extracted/GAME4/jobs/scripts/city_setup/level_transitions'
    for path in sorted(root.glob('*.sf')):
        text=path.read_text(encoding='utf-8-sig')
        def symbols(kind):return re.findall(r'\b'+kind+r'\s+\w+\s*\(\s*"([^"]+)"',text)
        transitions.append(dict(source=path.relative_to(WORLD/'notes/extracted').as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            hotspots=symbols('HotSpot'),doors=symbols('Gizmo'),locators=symbols('Locator'),jobs=symbols('Job'),
            states=re.findall(r'\bState\s+(\w+)\s*\(',text),
            edges=[dict(source=state[1],target=target[1])
                   for state in re.finditer(r'\bState\s+(\w+)\s*\([^\)]*\)(.*?)(?=\bState\s+\w+\s*\(|\Z)',text,re.S)
                   for target in re.finditer(r'\bgoto\s+(\w+)\s*\(',state[2])]))
    graph=dict(version=1,provenance='native developer presets and transition scripts; not a write recipe',
               native_entry_gate_implemented=False,presets=presets,transitions=transitions)
    (out/'story_graph.json').write_text(json.dumps(graph,indent=2),encoding='utf-8')
    counts=dict(locations=len(locations),items=len(items),categories=dict(Counter(r['category'] for r in locations.values())),
        source_status=dict(Counter(r['status'] for r in locations.values())),
        supported_items=sum(r['supported'] for r in effects),source_requirements=sum(bool(r['requirement']) for r in coverage),
        presets=len(presets),transition_scripts=len(transitions))
    (out/'coverage_summary.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')
    print(json.dumps(counts,indent=2))


if __name__=='__main__':main()
