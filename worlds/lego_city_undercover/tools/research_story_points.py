"""Review every Sheet story point; enable only explicit original completion events."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from collections import defaultdict
WORLD=Path(__file__).resolve().parents[1];ROOT=WORLD.parents[1]
JOB='Flow_Setup.Flow_Completed'
# Reviewed end-of-action fields, not current chapter/mission-stage thresholds.
REVIEWED={
 (2,'Auburn Bay Bridge Chaos Resolved'):'Act_1_RoadBlockRemoved',
 (2,'Grapple Gun'):'Act_1_GetGrappleGun',
 (5,'Steal the Car for Chan Chuang'):'Act_2_StealACar_4',
 (6,"Stop the Delivery Truck and bring it to Vinnie's Restaurant"):'Act_2_DeliveryTruck_2',
 (6,'Deliver the Bell Pepper Emerald to the Drop-off Location'):'Act_2_DropOffEmerald',
 (6,"Take all Photos of Chan's Gang Members and arrest them"):'Act_2_PhotographChansMen_2',
 (7,'Avoid Apollo Island Security'):'Act_2_SpaceIslandEscape',
 (8,'Drive Forrest Blackwell to the Police Station'):'Act_2_SaveForestBlackwell_2',
 (10,'Drop the T-Rex off at the Airport'):'Act_3_DeliverT-Rex',
 (10,'Rescue Natalia from the Hospital Rooftop'):'Act_3_Hospital_2',
 (10,'Fly Natalia to Safety'):'Act_3_FlyEllie',
 (12,'Drive the Telescope to the Drop-off Point'):'Act_4_StealTelescope_3',
 (14,"Reach Professor Kowalski's Lab"):'Act_4_DriveToKowalski',
 (14,'Assemble the Shield Generators around Blackwell Tower'):'Act_4_BlackwellTowerSaveCity_2',
}
ASSIGNMENTS=('rooftops','prison','mine','temple','bank','space_centre','scrapyard','museum','fire_station','blackwells_mansion_1','icecream_parlour','construction_site','secretbase','blackwells_mansion_2','moon_base')
BUILDS={'Build the Call Point at the Gas Station':'WI_FL_0708_VehDrop','Build the Ferry to Albatross Island':'SF_RD_0823_Ferry',
 'Build the Cable Car in the Mines':'Mine_CableCar','Build the Dragon in the Temple':'Temple_Dragon',
 'Build the Relocator inside the Bank':'Bank_Truck','Build the Car Crusher in the Scrapyard':'Scrapyard_Crusher',
 'Build the Yellow Devil in the Museum':'Museum_Plane','Build the T-Rex in the Museum':'Museum_Dinosaur',
 'Build the Industrial Crane on the Construction Yard':'Construction_Crane','Build the Space Shuttle':'IS_SC_3323_SpaceShuttle'}

def uncomment(text):
 return re.sub(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*.*?\*/',lambda m:m.group() if m.group().startswith(chr(34)) else '\n'*m.group().count('\n'),text,flags=re.S)

def writers(root):
 result=defaultdict(list)
 for path in root.rglob('*.sf'):
  relative=path.relative_to(root).as_posix()
  if any(x in relative.lower() for x in ('debug','archive','obsolete','_old')):continue
  raw=path.read_bytes()
  try:text=raw.decode('utf-8-sig')
  except UnicodeDecodeError:text=raw.decode('cp1252')
  text=uncomment(text);decl=defaultdict(set)
  for var,job in re.findall(r'Job\s+(\w+)\s*\(\s*"([^"]+)"\s*\)',text):decl[var].add(job)
  for m in re.finditer(r'(\w+)\.SetValue\(\s*"([^"]+)"\s*,\s*(true|false)\s*\)',text):
   var,field,value=m.groups()
   if decl.get(var)!={JOB}:continue
   states=list(re.finditer(r'(?m)^\s*(?:State|Function)\s+(\w+)\s*\(',text[:m.start()]))
   result[field].append(dict(resource='GAME4/jobs/scripts/'+relative,line=text.count('\n',0,m.start())+1,
    state=states[-1][1] if states else None,value=value=='true',source_sha256=hashlib.sha256(raw).hexdigest()))
 return result

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--sheet',type=Path,default=ROOT/'build/lego_city_undercover/story_pass_20261121/story_progression_sheet.json');args=parser.parse_args()
 values=json.loads(args.sheet.read_text())['values'];cat=json.loads((WORLD/'catalogue.json').read_text())['locations']
 schema={r['name']:{f['name']:f for f in r['fields']} for r in json.loads((WORLD/'notes/analysis/job_data.json').read_text())}
 evidence=writers(WORLD/'notes/extracted/GAME4/jobs/scripts');rows=[]
 for column,header in enumerate(values[0]):
  chapter=column+1 if column<15 else None
  for number,cells in enumerate(values[1:],2):
   if column>=len(cells) or not cells[column]:continue
   name=cells[column];key=None;kind='unresolved';field=REVIEWED.get((chapter,name));proof=[]
   match=re.search(r'Special Assignment #(\d+) (Start|Complete)',name)
   if match:
    key='mission:'+ASSIGNMENTS[int(match[1])-1]+':Complete' if match[2]=='Complete' else None
    kind='existing_location' if key else 'entry_control_event'
   elif name.startswith('Chapter ') or name=='Brick Multiplier x2':kind='internal_control_event'
   elif name in {'Police Outfit','Robber Outfit','Miner Outfit','Astronaut Outfit','Farmer Outfit','Firefighter Outfit','Construction Outfit'}:
    model={'Police Outfit':'COP','Robber Outfit':'ROBBER','Miner Outfit':'MINER','Astronaut Outfit':'ASTRONAUT',
      'Farmer Outfit':'FARMER','Firefighter Outfit':'FIREMAN','Construction Outfit':'CONSTRUCTION_LEGOCITYCONSTRUCTIONWORKER'}[name]
    key='story_disguise:'+model;kind='existing_location'
   elif name in BUILDS:
    key='objective:'+BUILDS[name];kind='existing_location'
   elif name.startswith('Clown Robber #'):
    key='story_arrest:clown_'+name[-1];kind='existing_location'
   elif field:
    proof=evidence.get(field,[]);definition=schema[JOB][field]
    if proof and all(r['value'] and r['state'] for r in proof) and definition['kind']=='Bool' and definition['marker']==1:
     key='story_point:'+JOB+':'+field;kind='native_job_completion'
   if key and kind=='existing_location' and key not in cat:raise ValueError('Missing existing location: '+key)
   apid=cat[key]['id'] if key in cat else 1000000000+int.from_bytes(hashlib.sha256(key.encode()).digest()[:4],'little')%900000000 if key else None
   rows.append(dict(point_key=key or 'chapter_'+str(chapter or 'postgame')+':'+re.sub(r'[^a-z0-9]+','_',name.casefold()).strip('_'),chapter=chapter,name=name,
    sheet_cell=chr(65+column)+str(number),kind=kind,ap_key=key,ap_id=apid,job=JOB if field else None,field=field,
    field_type='Bool' if field else None,expected_value=True if field else None,evidence=proof,
    check_eligible=kind in ('native_job_completion','existing_location'),new_location=kind=='native_job_completion',
    verification='native_binding_verified' if kind=='native_job_completion' else 'static_source_only',
    native_restart_persistence_live_verified=False,write_safe=False,
    detection_strategy='typed named JobValue; durable outgoing journal' if kind=='native_job_completion' else kind,
    todo=None if kind in ('existing_location','native_job_completion') else
      'Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence' if kind=='unresolved' else
      'Implement original chapter/mission entry control; never generate an automatic duplicate check'))
 if len({r['ap_id'] for r in rows if r['new_location']})!=sum(r['new_location'] for r in rows):raise ValueError('Duplicate new story point IDs')
 result=dict(version=1,source_sheet='Story Progression',source_spreadsheet='1dt-6qi7bvCcV1975xHqtpiqgebrzzFjBk9wXfGIvn3I',points=rows)
 (WORLD/'bridge/story_point_bindings.json').write_text(json.dumps(result,indent=2)+'\n')
 print(str(len(rows))+' Sheet milestones; '+str(sum(r['new_location'] for r in rows))+' source-backed new completion checks; '+str(sum(r['kind']=='existing_location' for r in rows))+' existing checks reused')
if __name__=='__main__':main()
