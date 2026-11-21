"""Export story review, exact pending work and non-destructive Sheet row patches."""
import csv
import json
from pathlib import Path
WORLD=Path(__file__).resolve().parents[1]
HEADER=['No.','Category','Area','Location / Check','Tools','Abilities','Auras','Build Cost ??','Notes','','AP Key / Source','Resource / Position','Mission / Group','Native District / Region','Internal Area / Tile','Native Hash / Bit','Check Status','Area Evidence','Source','Original Category','Technical Notes']
def csvfile(path,columns,rows):
 with path.open('w',encoding='utf-8-sig',newline='') as stream:
  writer=csv.writer(stream);writer.writerow(columns);writer.writerows(rows)
def main():
 out=WORLD/'docs/research/story_control';out.mkdir(parents=True,exist_ok=True)
 points=json.loads((WORLD/'bridge/story_point_bindings.json').read_text())['points']
 builds=json.loads((WORLD/'bridge/mission_superbuild_bindings.json').read_text())
 design=json.loads((WORLD/'bridge/location_design.json').read_text())['rows'];existing={r['native_key']:r for r in design if r['native_key']}
 columns=['point_key','chapter','name','sheet_cell','kind','ap_key','ap_id','job','field','field_type','verification','check_eligible','native_restart_persistence_live_verified','write_safe','evidence','todo']
 csvfile(out/'story_point_review.csv',columns,[[json.dumps(r.get(c),ensure_ascii=False) if c=='evidence' else r.get(c) for c in columns] for r in points])
 pending=[r for r in points if r['todo']]
 csvfile(out/'story_point_todo.csv',columns,[[json.dumps(r.get(c),ensure_ascii=False) if c=='evidence' else r.get(c) for c in columns] for r in pending])
 number=max(int(r['number']) for r in design)+1;patches=[]
 for point in points:
  if not point['new_location']:continue
  old=existing.get(point['ap_key']);source=point['evidence'][0]
  row=[old['number'] if old else number,'Story Milestone','Story Chapter '+str(point['chapter']),point['name'],'','','','',
   'Native completion detected independently of AP item ownership. Traversal requirements remain unverified.','',point['ap_key'],
   source['resource']+':'+str(source['line']),'Chapter '+str(point['chapter']),'',point['job'],point['field'],
   'Typed native completion; individual live action test pending','Not inferred from chapter',source['resource'],'story_milestones',
   'AP ID '+str(point['ap_id'])+'; '+point['job']+'.'+point['field']+' == true; read only; provisional locations hold no progression items']
  patches.append(['update' if old else 'append',old['sheet_row'] if old else '',*row])
  if not old:number+=1
 for build in builds:
  key='objective:'+build['objective'];old=existing.get(key)
  row=[old['number'] if old else number,'Story Super Build',build['mission'],build['objective'],'SuperBuild','','',build['build_cost'],
   'Existing AP location; extend detector rather than create a duplicate city/build check.','',key,build['script'],build['mission'],'',build['scene'],
   build['native_suffix'],'Exact mission/scene/template identity; non-mine live build test pending',
   'Original script and builder template',build['script'],'super_builds',
   'AP ID '+str(build['ap_id'])+' retained; native state 5 and flag 4; replay backfill requires observed event journal']
  patches.append(['update' if old else 'append',old['sheet_row'] if old else '',*row])
  if not old:number+=1
 csvfile(out/'locations_sheet_patch.csv',['operation','existing_sheet_row',*HEADER],patches)
 csvfile(out/'mission_superbuild_review.csv',list(builds[0]),[[r[c] for c in builds[0]] for r in builds])
 lines=['# Remaining story control work','',
  'This list is explicit unfinished implementation, not a claim that native Open World or a pause-menu chapter selector exists.','',
  '## P0: original pause menu and independent chapters','',
  '- [ ] Implement the actual native pause-menu entry factory and submenu lifecycle: frontendmain.baml nodes, PauseMenuDrawer ownership, input/controller focus, activation callback and teardown. Root drawer lookup at 0x79377 is NOT an entry-creation API. No external chapter window is a substitute.',
  '- [ ] Implement all 15 chapter activation transactions using original flow transitions. Achievements_MarkChapterStart (0x84f0) records event flags; it does not select/start a chapter. Preserve permanent Flow_Completed, assignment completion, shield/Hero/token states and AP outgoing checks.',
  '- [ ] Establish an isolated per-save chapter model. Achievements complete (0x84b0 -> 0x7cf0) writes LegoAchievements +0x110 / +0x188, but per-save/Steam isolation is not verified. The event reader never queues chapter-completion checks or infers an active chapter.',
  '- [ ] Validate abort/resume/replay and Chapter 6 -> 3 -> 6, then Chapters 12?15, including both mansion assignments and timed/automatic transitions. Do not erase story history or bulk-apply developer presets.','',
  '## P0: coherent native Open World initialization','',
  '- [ ] Determine a reversible minimal initialization for PDA/map, police HQ, traffic/population, city jobs, bridges/travel, save setup and chapter selection without granting tools or completing story flags. Existing narrowly scoped HQ/SuperBuild fixes remain intact.',
  '- [ ] Native Open World remains unsupported; normal new seeds now reject it. experimental_items retains only explicit AP-graph research compatibility, not a native feature. Existing seeds/IDs are not migrated silently.','',
  '## P1: pre-consumption native access and travel','',
  '- [ ] Bind chapter/assignment hotspot and invitation eligibility before StartLevel is consumed. Cover normal/replay/summary/automatic/split-screen routes and rearm a denied interaction after receipt. Blocking final Door::Trigger is insufficient.',
  '- [ ] Map legacy Story Access assignment IDs to real native effects before enabling them in ordinary seeds. Do not add ineffective progression tickets.',
  '- [ ] Implement native destination selection checks for train/ferry/map/scripted travel and safe profile-bound reload recovery. Keep the 90 m guard and existing near-boundary/vehicle/creature restrictions until validated.',
  '- [ ] Execute the existing foot/run/jump/car/bike/bus/boat/air/hover/passenger/rail/pig/Behemoth matrix, including physics/controls/save feedback; RPC success is not a gameplay verdict.','',
  '## P1: mission constructions and reward evidence','',
  '- [ ] Live-test the six newly source-bound non-mine mission builds: exact owner scene, runtime name, native cost, final state and flag; test two matching instances are quarantined rather than guessed.',
  '- [ ] Establish independent native persistence for every mission build. Until then the durable AP queue preserves observed completions only; do not infer construction from mission completion or disappearance.',
  '- [ ] Investigate inactive Fire Extender references and the Scrapyard crane template. A referenced template/disabled script is not an independently collectible Super Build. Do not add locations without a genuine construction event.',
  '- [ ] Paradise Pool/Space Shuttle/Serenity Bridge candidates must be reconciled with the 65 city jobs before adding another story location.',
  '- [ ] Recheck existing story disguise detectors when the class was already AP-owned. Only the scoped COP/PDA recovery has specific earlier evidence; independent source events remain required for the other outfits.','',
  '## Per-Sheet-point outstanding work','',
  'All 150 Sheet points are in story_point_review.csv. Fourteen source-bound actions are implemented; 35 points reuse existing IDs. Starts/completions remain control events, not automatic extra checks.','',
  '| Chapter | Sheet cell | Point | Remaining work |','|---|---|---|---|']
 for r in pending:lines.append('| '+str(r['chapter'] or 'Post Game')+' | '+r['sheet_cell']+' | '+r['name'].replace('|','/')+' | '+r['todo'].replace('|','/')+' |')
 (out/'TODO.md').write_text('\n'.join(lines)+'\n')
 print(str(len(points))+' reviewed points; '+str(len(pending))+' explicit pending rows; '+str(len(patches))+' offline Sheet patches; online Sheet unchanged')
if __name__=='__main__':main()
