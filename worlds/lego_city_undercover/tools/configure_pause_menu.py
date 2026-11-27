"""Install/query the pinned original pause-menu extension via the existing native RPC.

Does not attach a debugger, synthesize input, grant items or write save files.
Chapter entries are shown disabled until native activation is implemented.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'worlds/lego_city_undercover/bridge'))
from live_monitor import Session
from native_model_transport import configure_pause_menu,replace_pause_menu
from native_build_integrity import bridge_health


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disable',action='store_true')
    parser.add_argument('--query',action='store_true')
    parser.add_argument('--replace-build',type=Path,help='Previous verified build manifest for an explicit live UI handoff')
    args=parser.parse_args()
    problem=bridge_health(ROOT)
    if problem:raise RuntimeError(problem)
    manifest=json.loads((ROOT/'build/lego_city_undercover/native_items_build.json').read_text(encoding='utf-8'))
    session=Session()
    try:
        dll=ROOT/'build/lego_city_undercover'/manifest['dll_filename']
        if args.replace_build:
            if args.disable or args.query:raise ValueError('Replacement cannot be combined with query/disable')
            old=json.loads(args.replace_build.read_text(encoding='utf-8'))
            if Path(old['dll_filename']).name!=old['dll_filename']:raise ValueError('Invalid previous DLL filename')
            result=replace_pause_menu(session.pid,dll,dll.parent/old['dll_filename'],old['dll_sha256'])
        else:
            result=configure_pause_menu(session.pid,dll,not args.disable,query=args.query)
        print(json.dumps(result,indent=2))
    finally:session.close()
