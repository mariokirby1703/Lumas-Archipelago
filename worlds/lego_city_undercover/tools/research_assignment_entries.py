"""Derive all 15 replay entrance identities from the original city script.

Exports metadata only. Does not patch scripts or claim native gate installation.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

WORLD=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from goals import ASSIGNMENTS


def parse_entries(text,items):
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    arrays={name:re.findall(r'\b'+name+r'\.Add\(\s*"([^"]+)"\s*\)',text)
            for name in ('caHotSpots','caMapPins','caMission')}
    if any(len(values)!=15 for values in arrays.values()):
        raise ValueError('Expected exactly 15 original assignment entries')
    entries={}
    for match in re.finditer(r'Function\s+(FN_\w+)\(\)\s*\{(.*?)\n\};',text,re.S):
        body=match[2]
        index=re.search(r'tHotspot\s*=\s*caHotSpots.Get\((\d+)\)',body)
        if not index:continue
        i=int(index[1])
        if i not in range(15) or i in entries:raise ValueError('Duplicate/out-of-range entry')
        if not re.search(r'tMission\s*=\s*caMission.Get\('+str(i)+r'\)',body):
            raise ValueError('Mission/hotspot index mismatch')
        fields={name:re.findall(r'\b'+name+r'\s*=\s*"([^"]*)"',body)
                for name in ('tAreaName','tExitToDoor','tExternalDoor','tCutscene')}
        if any(len(v)!=1 for v in fields.values()):raise ValueError('Ambiguous destination')
        assignment=ASSIGNMENTS[i]
        if fields['tAreaName'][0].lower()!=assignment:raise ValueError('Assignment order mismatch')
        item='Story Access: '+assignment
        entries[i]=dict(number=i+1,assignment=assignment,item=item,item_id=items[item]['id'],
            hotspot=arrays['caHotSpots'][i],map_pin=arrays['caMapPins'][i],
            story_job=arrays['caMission'][i],callback=match[1],
            area=fields['tAreaName'][0],exit_door=fields['tExitToDoor'][0],
            external_door=fields['tExternalDoor'][0],cutscene=fields['tCutscene'][0])
    if set(entries)!=set(range(15)):raise ValueError('Incomplete original callback map')
    return [entries[i] for i in range(15)]


def main():
    relative='GAME4/jobs/scripts/city_setup/level_transitions/level_transitions.sf'
    source=WORLD/'notes/extracted'/relative
    data=source.read_bytes()
    catalogue=json.loads((WORLD/'catalogue.json').read_text())
    report=dict(version=1,source=relative,sha256=hashlib.sha256(data).hexdigest(),
                native_entry_enforcement=False,entries=parse_entries(data.decode('utf-8-sig'),catalogue['items']))
    (WORLD/'bridge/assignment_entries.json').write_text(json.dumps(report,indent=2)+'\n')
    print('15 original replay callback/destination mappings; no native hook installed')

if __name__=='__main__':main()
