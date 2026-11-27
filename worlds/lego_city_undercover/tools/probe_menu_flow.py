"""Observe native frontend page objects without attaching a debugger."""
import json
from pathlib import Path
import sys
WORLD=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from live_monitor import Session
from menu_flow_reader import read_menu_flow

def main():
    session=Session()
    try:
        result=read_menu_flow(session.read,session.base)
        result.update(pid=session.pid,writes_enabled=False)
        output=WORLD.parents[1]/'build/lego_city_undercover/debugger/menu_flow_observation.json'
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(dict(status=result['status'],pid=session.pid,
            entries=[len(t['entries']) for t in result.get('tables',[])],writes_enabled=False),indent=2))
    finally:session.close()

if __name__=='__main__':main()
