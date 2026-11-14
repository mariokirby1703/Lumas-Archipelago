"""Start the opt-in native AP client without shell-interpolating server input."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connect');parser.add_argument('--name')
    parser.add_argument('--native-save-file',type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[3]
    sys.path.insert(0,str(root/'worlds/lego_city_undercover/bridge'))
    from native_bridge_path import bridge_path
    dll=bridge_path(root)
    if not dll.is_file():parser.error('Build LCUItemBridge.dll with tools/build_item_bridge.py first')
    server=args.connect or input('AP-Server (Host:Port): ').strip()
    name=args.name or input('AP-Slotname: ').strip()
    if not server or not name:parser.error('Server and slot name are required')
    command=[sys.executable,str(root/'worlds/lego_city_undercover/Client.py'),
             '--connect',server,'--name',name,'--enable-native-items','--enable-cutscene-skip']
    if args.native_save_file:command+=['--native-save-file',str(args.native_save_file.resolve())]
    return subprocess.call(command,cwd=root,env=dict(os.environ,SKIP_REQUIREMENTS_UPDATE='1'))


if __name__=='__main__':raise SystemExit(main())
