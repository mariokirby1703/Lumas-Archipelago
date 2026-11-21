"""Match original mission scripts, builder templates and exact source object names."""
import hashlib
import json
import math
from pathlib import Path
import re
import struct
from resource_catalogue import sections
WORLD=Path(__file__).resolve().parents[1]
SPECS=(
 ('mine','mine_cavern','cablecar','Mine_CableCar','level11.sf','iCABLECAR_SUPERBUILDIT_CMPLX'),
 ('temple','temple_courtyard','dragon','Temple_Dragon','level1.sf',''),
 ('bank','bank_interior','truck','Bank_Truck','level12.sf','SB_Truck'),
 ('construction_site','construction_site_02','crane','Construction_Crane','level1.sf','iSB_Crane'),
 ('museum','museum_room01','yellow_devil','Museum_Plane','level16.sf','iYellow_Devil'),
 ('museum','museum_room02','t_rex','Museum_Dinosaur','level1.sf','iT-Rex_SuperBuild'),
 ('scrapyard','scrapyard_entrance','carcrusher','Scrapyard_Crusher','level1.sf','iCar_Crusher'),
)

def parse_template(payload):
 if len(payload)<64 or struct.unpack_from('<II',payload)!=(8,1):raise ValueError('Unsupported Superbuild template')
 names=[]
 for i in range(24,len(payload)-22):
  length=payload[i]
  if not 2<=length<=32 or i+1+length+22!=len(payload):continue
  raw=payload[i+1:i+1+length]
  if raw[-1:]!=b'\0' or not re.fullmatch(rb'[A-Za-z_][A-Za-z_0-9-]+',raw[:-1]):continue
  names.append(raw[:-1].decode('ascii'))
 if len(names)!=1:raise ValueError('Ambiguous template object footer')
 cost=struct.unpack_from('<f',payload,24)[0]
 if not math.isfinite(cost) or not cost.is_integer() or not 0<=cost<=1000000:raise ValueError('Invalid native build cost')
 return names[0],int(cost)

def main():
 extracted=WORLD/'notes/extracted';catalogue=json.loads((WORLD/'catalogue.json').read_text())['locations'];result=[]
 for mission,scene,template,objective,script_name,alias in SPECS:
  root=next(extracted.glob('*/levels/standalones/'+mission+'/'+scene))
  candidates=list((root/'ai').glob('*.sf'))
  scripts=[p for p in candidates if '"'+objective+'"' in p.read_text(errors='replace') and re.search(r'gSuperbuild\.GetOutput\(\s*[123]\s*\)',p.read_text(errors='replace'),re.I)]
  if len(scripts)!=1:raise ValueError('Need unique original completion script: '+objective)
  script=scripts[0];text=script.read_text();targets=re.findall(r'SetSuperBuildTarget\(\s*(\d+)\s*\)',text)
  declared=re.findall(r'Gizmo\s+gSuperbuild\s*\(\s*"([^"]+)"',text,re.I)
  if len(set(declared))!=1:raise ValueError('Ambiguous original superbuild reference')
  alias=declared[0]
  source=extracted/'GAME4/levels/builder'/('builder_sb_'+template)/('builder_sb_'+template+'.giz')
  data=source.read_bytes();part=next(p for p in sections(data)[0] if p['name']=='GizSuperBuild')
  name,cost=parse_template(data[part['offset']:part['offset']+part['size']])
  if targets and any(int(v)!=cost for v in targets):raise ValueError('Script/template cost conflict: '+objective)
  row=catalogue['objective:'+objective]
  result.append(dict(mission=mission,scene=scene,native_suffix=name,native_alias=alias,objective=objective,ap_id=row['id'],
   source=source.relative_to(extracted).as_posix(),script=script.relative_to(extracted).as_posix(),script_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
   build_cost=cost,completion_state=5,completion_flag=4,loaded_instance_required=True,
   persistence='durable AP outgoing journal after observed native completion; independent native replay flag unproven',
   verification='native_binding_candidate',live_gameplay_verified=objective=='Mine_CableCar'))
 for binding in result:
  row=catalogue['objective:'+binding['objective']]
  source=Path(binding['script']).parent.parent/(binding['scene']+'.giz')
  row.update(source=source.as_posix(),mission=binding['mission'],section=binding['scene'],
   mission_superbuild=True,building_brick_cost=dict(amount=binding['build_cost'],evidence='original script/template agreement',logic_enforced=False),
   native_build_identity=dict(scene=binding['scene'],name=binding['native_suffix'],template=binding['source']),
   completion_evidence='native state 5 / completion flag 4; original scanner flag may remain unset')
 full=json.loads((WORLD/'catalogue.json').read_text());full['locations']=catalogue
 (WORLD/'catalogue.json').write_text(json.dumps(full,indent=2,sort_keys=True)+'\n')
 (WORLD/'bridge/mission_superbuild_bindings.json').write_text(json.dumps(result,indent=2)+'\n')
 print(str(len(result))+' exact mission/script/template bindings; original locations/IDs retained')
if __name__=='__main__':main()

