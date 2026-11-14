"""Recover only earned station checks into the matching AP journal; no game writes."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys
from datetime import datetime, timezone

WORLD=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from live_monitor import Session
from inventory_reader import pointer
from story_reader import read_story
from delivery_marker import MARKER_OFFSET,MARKER_SIZE,parse_marker,binding_token
from client_checks import changed_checks
from client_journal import Journal
from station_rewards import STATION_REWARD_KEYS


def recover(apply=False):
    session=Session()
    try:
        bank=pointer(session.read,session.base+0x1c7cbb8)
        marker=parse_marker(session.read(bank+MARKER_OFFSET,MARKER_SIZE)) if bank else None
        if not marker:raise RuntimeError('No loaded AP save identity; no checks queued')
        story=read_story(session.read,session.base)
        directory=WORLD/'notes/client_journal'
        matches=[]
        for path in directory.glob('*.sqlite3'):
            connection=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
            try:
                row=connection.execute('SELECT value FROM metadata WHERE key=?',('binding',)).fetchone()
                if row:
                    binding=json.loads(row[0])
                    if binding_token(binding).hex()==marker['binding']:matches.append((path,binding))
            finally:connection.close()
        if len(matches)!=1:raise RuntimeError('Loaded save does not match exactly one AP journal')
        path,binding=matches[0]
        active={key:row for key,row in binding['catalogue'].items() if row.get('key') in STATION_REWARD_KEYS}
        connection=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
        try:checked={row[0] for row in connection.execute('SELECT location FROM outgoing WHERE acknowledged=1')}
        finally:connection.close()
        snapshot=dict(objectives=dict(status='read',records=[]),pickup_bits=[],story=story)
        checks,_=changed_checks(active,None,snapshot,checked)
        report=dict(time=datetime.now(timezone.utc).isoformat(),pid=session.pid,
                    seed=binding['seed'],team=binding['team'],slot=binding['slot'],
                    journal=path.name,save_binding=marker['binding'],pda=story.get('jobs',{}).get('PDA',{}),
                    checks=checks,locations={key:row['name'] for key,row in active.items()},
                    applied=False,game_writes=False)
        if apply and checks:
            # The ordinary client already reads/sends pending journal entries.
            # Verify the native save is still the same before committing.
            if parse_marker(session.read(bank+MARKER_OFFSET,MARKER_SIZE))['binding']!=marker['binding']:
                raise RuntimeError('Loaded save identity changed before recovery')
            journal=Journal(directory,binding)
            try:
                if journal.binding_token.hex()!=marker['binding']:raise RuntimeError('Journal identity changed')
                journal.queue(checks)
            finally:journal.close()
            report['applied']=True
        output=WORLD.parents[1]/'build/lego_city_undercover/station_reward_recovery.json'
        output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))
        return report
    finally:session.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    recover(parser.parse_args().apply)
