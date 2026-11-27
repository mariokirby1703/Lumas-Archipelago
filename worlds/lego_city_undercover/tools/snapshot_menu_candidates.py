"""Capture extended GUI2Menu candidate state, read-only and without debugger.

Source method 0x556780 accesses +0x230, beyond the earlier +0x220 capture.
Vtable candidates are not proof of visibility. No AP checks or writes are made.
"""
import argparse
import json
from pathlib import Path
import re
import struct
import sys
WORLD=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from live_monitor import Session

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label');args=parser.parse_args()
    if not re.fullmatch('[a-z0-9_-]{1,40}',args.label):parser.error('Invalid snapshot label')
    root=WORLD.parents[1]/'build/lego_city_undercover/debugger'
    source=json.loads((root/'nearby_menu_candidates.json').read_text())
    session=Session();rows=[]
    try:
        if session.pid!=source['pid']:raise RuntimeError('Process changed; rebuild candidate list')
        for row in source['candidates']:
            if row['kind']!='GUI2Menu':continue
            address=int(row['address'],16);raw=session.read(address,0x350)
            if struct.unpack_from('<Q',raw)[0]!=session.base+0xcf5c58:continue
            if session.read(address,8)!=raw[:8]:raise RuntimeError('Menu candidate changed during read')
            rows.append(dict(row,data=raw.hex(),field_230=struct.unpack_from('<I',raw,0x230)[0]))
        report=dict(pid=session.pid,label=args.label,rows=rows,writes_enabled=False,visibility_verified=False)
        (root/('menu_candidates_'+args.label+'.json')).write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(dict(pid=session.pid,count=len(rows),fields_230=[r['field_230'] for r in rows]),indent=2))
    finally:session.close()

if __name__=='__main__':main()
