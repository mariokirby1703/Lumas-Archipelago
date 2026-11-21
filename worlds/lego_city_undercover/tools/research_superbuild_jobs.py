"""Derive persistent city Superbuild/job pairs from original completion states.

Only explicit CityObjective_SetComplete + nState=2 in the same named state
are accepted. Source text remains in ignored notes; packaged output is metadata.
"""
import json
from pathlib import Path
import re
import sys
from archive_index import parse_index,extract
WORLD=Path(__file__).resolve().parents[1]

def uncomment(text):
    return re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/',lambda m:m.group() if m.group().startswith(chr(34)) else '\n'*m.group().count('\n'),text,flags=re.S)

def pairs(text):
    text=uncomment(text)
    declarations=dict(re.findall(r'CityObjective\s+(\w+)\s*\(\s*"([^"\n]+)"\s*\)',text))
    jobs=dict(re.findall(r'Job\s+(\w+)\s*\(\s*"(SuperBuild_Saves\.[^"\n]+)"\s*\)',text))
    states=list(re.finditer(r'(?m)^\s*State\s+(\w+)\s*\(',text))
    result=set()
    for i,state in enumerate(states):
        body=text[state.start():states[i+1].start() if i+1<len(states) else len(text)]
        completed={declarations[v] for v in re.findall(r'CityObjective_SetComplete\(\s*(\w+)\s*\)',body) if v in declarations}
        written={jobs[v] for v in re.findall(r'(\w+)\.SetValue\(\s*"nState"\s*,\s*2\s*\)',body) if v in jobs}
        if len(completed)==len(written)==1:result.add((next(iter(written)),next(iter(completed))))
    return result

def main():
    archive=WORLD/'notes/gamefiles/GAME5.DAT'
    entries=parse_index((WORLD/'notes/analysis/GAME5.DAT.index').read_bytes(),archive.stat().st_size)
    evidence={};reward_models={}
    for entry in entries:
        name=entry.get('path') or ''
        if not name.endswith('.sf') or '/lego_city/lego_city/' not in name.replace('\\','/'):continue
        raw=extract(archive,entry)
        if b'SuperBuild_Saves' not in raw:continue
        text=uncomment(raw.decode('utf-8-sig'))
        for job,objective in pairs(text):
            models=set(re.findall(r'SuperCounterUI(?:AndAnim)?\(\s*#SuperBuild\s*,[^;]*?false\s*,\s*"([^"]+)"',text))
            if len(models)==1:reward_models.setdefault(job,set()).update(m.upper() for m in models)
            evidence.setdefault((job,objective),[]).append('GAME5/'+name.replace('\\','/'))
    # Two tutorial-specific scripts use Text arguments and separate state blocks.
    tutorials=[('SuperBuild_Saves.SF_Residential.0823_Ferry','SF_RD_0823_Ferry','find_ferry/superbuild_watch.sf'),
        ('SuperBuild_Saves.WI_Farmlands.0708_VD','WI_FL_0708_VehDrop','vehicle_drop_info/vehicledrop_intro.sf')]
    for job,objective,source in tutorials:
        path=WORLD/'notes/extracted/GAME4/jobs/scripts'/source;text=path.read_text()
        if job not in text or objective not in text or not re.search(r'SetValue\(\s*"nState"\s*,\s*2\s*\)',text):
            raise ValueError('Tutorial evidence changed: '+source)
        # The gas-station tile contains a copied SF_RD_0922_VehDrop target.
        # Its dedicated story script is authoritative for this one known mismatch.
        for previous in list(evidence):
            if previous[0]==job and previous[1]!=objective:
                if job!='SuperBuild_Saves.WI_Farmlands.0708_VD' or previous[1]!='SF_RD_0922_VehDrop':
                    raise ValueError('Unreviewed tutorial conflict: '+str(previous))
                del evidence[previous]
        models=set(re.findall(r'SuperCounterUI(?:AndAnim)?\(\s*#SuperBuild\s*,[^;]*?false\s*,\s*"([^"]+)"',uncomment(text)))
        if len(models)==1:reward_models.setdefault(job,set()).update(m.upper() for m in models)
        evidence.setdefault((job,objective),[]).append('GAME4/jobs/scripts/'+source)
    schema={r['name']:{f['name']:f for f in r['fields']} for r in json.loads((WORLD/'notes/analysis/job_data.json').read_text())}
    catalogue=json.loads((WORLD/'catalogue.json').read_text())['locations'];rows=[];seen=set()
    for (job,objective),resources in sorted(evidence.items()):
        fields=schema[job]
        if fields['nState']['kind']!='Int' or fields['nState']['marker']!=1:raise ValueError('Unreviewed persistence field')
        if job in seen:raise ValueError('Ambiguous job/objective association: '+job+' / '+objective)
        seen.add(job)
        target=catalogue['objective:'+objective]
        if target['category']!='super_builds':raise ValueError('Not a Superbuild objective')
        rows.append(dict(job=job,objective=objective,native_id=fields['nID']['default'],completed_state=2,
            ap_id=target['id'],evidence=sorted(resources),verification='native_binding_verified',
            live_gameplay_verified=False,reward_model=next(iter(reward_models[job])) if len(reward_models.get(job,()))==1 else None))
    if {r['native_id'] for r in rows}!=set(range(1,66)):raise ValueError('Incomplete or duplicate 65-build job coverage: '+str(len(rows)))
    (WORLD/'bridge/superbuild_jobs.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(str(len(rows))+' persistent Superbuild job bindings; original AP IDs unchanged')
if __name__=='__main__':main()

