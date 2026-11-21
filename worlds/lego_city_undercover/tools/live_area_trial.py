"""Controlled, backed-up native Auburn/Cherry boundary trial; no AP receipts changed.

Requires operator to stand on safe Auburn ground and close the ordinary client.
This tool never records controls/physics as verified automatically.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sqlite3
import sys
import time
from types import SimpleNamespace
WORLD=Path(__file__).resolve().parents[1];ROOT=WORLD.parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from live_monitor import Session
from area_passes import AreaGate,START,FIRST,tile_district
from native_build_integrity import bridge_health
from native_save import resolve_save,read_save,ensure_backup
from delivery_marker import read_marker,marker_from_save,parse_marker

async def trial(seconds,output):
    problem=bridge_health(ROOT)
    if problem:raise RuntimeError(problem)
    manifest=json.loads((ROOT/'build/lego_city_undercover/native_items_build.json').read_text())
    dll=ROOT/'build/lego_city_undercover'/manifest['dll_filename']
    session=Session();gate=AreaGate();report={}
    try:
        initial=session.snapshot();marker=read_marker(session.read,session.base).get('marker')
        if not marker:raise RuntimeError('A bound AP test save is required')
        if (tile_district(initial.get('location',{}).get('native_tile'))!=START or
                initial.get('actor',{}).get('context',{}).get('index')!=46 or
                initial.get('ride',{}).get('status') not in ('not_mounted','expired_weak_reference')):
            raise RuntimeError('Stand unmounted on operator-confirmed safe Auburn ground first')
        path=resolve_save(session.read,session.base)
        if path.parent.name!='slot3':raise RuntimeError('Only the user-authorized test slot3 is permitted')
        data=read_save(path);disk_marker=parse_marker(marker_from_save(data))
        if not disk_marker or disk_marker['binding']!=marker['binding']:raise RuntimeError('Disk/live AP identity mismatch')
        output.parent.mkdir(parents=True,exist_ok=True)
        backup=ensure_backup(path,output.parent/'native_backup'/path.parent.name)
        journal=SimpleNamespace(binding_token=bytes.fromhex(marker['binding']),directory=None)
        report=dict(format='LCU controlled area trial',version=1,blocked=[FIRST],native_save=str(path),
            backup=str(backup),binding=marker['binding'],dll=manifest['dll_filename'],process=initial['process'],
            operator_confirmed_safe_start=True,controls_verified=False,physics_verified=False,
            native_save_after_verified=False,live_gameplay_verified=False,mutations='area checkpoint/near-boundary return only')
        end=time.monotonic()+seconds;last=None
        while time.monotonic()<end:
            snapshot=session.snapshot()
            current=(snapshot.get('native_binding') or {}).get('marker')
            if not current or current['binding']!=marker['binding'] or snapshot['process'].get('profile')!=initial['process'].get('profile'):
                raise RuntimeError('Save/profile identity changed; trial stopped')
            status=await gate.poll(session,snapshot,journal,[],dll,backup_ready=True)
            if status!=last:print(status,snapshot.get('location',{}).get('native_tile'),flush=True);last=status
            report['area_evidence']=gate.report()
            output.write_text(json.dumps(report,indent=2))
            if status in ('return_uncertain','return_rejected_safe','disembark_not_observed'):
                raise RuntimeError('Native trial stopped after '+status+'; no automatic replay')
            await asyncio.sleep(.25)
        print('Trial recorded; controls, collision and physics still require operator feedback.',flush=True)
    except Exception as error:
        report.update(error=str(error),area_evidence=gate.report(),live_gameplay_verified=False)
        output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2));raise
    finally:session.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds',type=int,default=60)
    parser.add_argument('--output',type=Path,default=ROOT/'build/lego_city_undercover/reliability_20261121/live_area_trial.json')
    args=parser.parse_args()
    if not 1<=args.seconds<=300:parser.error('Use 1..300 seconds for a controlled trial')
    asyncio.run(trial(args.seconds,args.output))
if __name__=='__main__':main()
