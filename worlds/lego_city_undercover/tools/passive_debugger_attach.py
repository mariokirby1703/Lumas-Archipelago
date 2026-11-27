"""Short, explicitly requested game attach/detach test without custom breakpoints.

Does not close the debugger. Process survival is not proof of game responsiveness.
"""
import argparse
import json
from pathlib import Path
import sys
import time

WORLD=Path(__file__).resolve().parents[1]
ROOT=WORLD.parents[1]
sys.path.insert(0,str(WORLD/'bridge'))

def main():
    from live_monitor import Session
    from x64dbg_automate import X64DbgClient
    import psutil
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--debugger-pid',type=int,required=True)
    args=parser.parse_args()
    build=ROOT/'build/lego_city_undercover/debugger'
    if (build/'live_probes_disabled.json').exists():
        raise RuntimeError('Live attachment disabled after a user-reported input freeze')
    c=X64DbgClient(str(build/'x64dbg/release/x64/x64dbg.exe'))
    session=None;attached=False
    report=dict(custom_breakpoints=False,engine_calls=False,save_writes=False,debugger_closed=False)
    try:
        session=Session()  # validates the actual running executable hash
        process=psutil.Process(session.pid);created=process.create_time()
        report.update(game_pid=session.pid,module_base=hex(session.base),created=created)
        entries={rva:session.read(session.base+rva,16) for rva in (0x797d0,0x7a270,0x1f9830,0x556770)}
        c.attach_session(args.debugger_pid)
        if c.is_debugging():raise RuntimeError('Debugger is occupied; leave it unchanged')
        if not c.attach(session.pid):raise RuntimeError('Attach failed')
        attached=True
        time.sleep(1)
        if not c.is_running():
            if not c.go() or not c.wait_until_running(3):raise RuntimeError('Resume before detach failed')
        report['running_before_detach']=c.is_running()
        report['detached']=c.detach();attached=not report['detached']
        if attached:raise RuntimeError('Detach failed')
        time.sleep(2)
        report['same_process_alive']=process.is_running() and process.create_time()==created
        report['observed_entry_bytes_unchanged']=all(session.read(session.base+rva,16)==raw for rva,raw in entries.items())
        report['menu_responsiveness']='requires player observation; not inferred from process survival'
    finally:
        if attached:
            if not c.is_running():c.go()
            report['cleanup_detached']=c.detach()
        c.detach_session()
        if session:session.close()
        (build/'passive_attach_result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
