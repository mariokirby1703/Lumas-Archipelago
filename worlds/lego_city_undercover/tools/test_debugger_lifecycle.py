"""Only attach to the child heartbeat executable created by this test."""
import argparse
import json
from pathlib import Path
import subprocess
import threading
import time
from x64dbg_automate import X64DbgClient

ROOT=Path(__file__).resolve().parents[3]
BUILD=ROOT/'build/lego_city_undercover/debugger'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--debugger-pid',type=int,required=True)
    args=parser.parse_args()
    target=(BUILD/'debugger_lifecycle_target.exe').resolve()
    child=subprocess.Popen([str(target)],stdout=subprocess.PIPE,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    ticks=[]
    def collect():
        for line in child.stdout:ticks.append(line.strip())
    reader=threading.Thread(target=collect,daemon=True);reader.start()
    c=X64DbgClient(str(BUILD/'x64dbg/release/x64/x64dbg.exe'))
    report=dict(target=str(target),target_pid=child.pid,debugger_pid=args.debugger_pid,game_attached=False)
    attached=False
    try:
        c.attach_session(args.debugger_pid)
        if c.is_debugging():raise RuntimeError('Refuse occupied debugger')
        if not c.attach(child.pid):raise RuntimeError('Test child attach failed')
        attached=True
        if c.is_running():c.pause()
        if not c.wait_until_stopped(5):raise RuntimeError('No test-child stop')
        address,valid=c.eval_sync('kernelbase.Sleep')
        if not valid or not address:raise RuntimeError('Sleep symbol unresolved')
        if not c.set_breakpoint(address,'isolated_lifecycle_probe'):raise RuntimeError('Breakpoint failed')
        c.cmd_sync('run')
        if not c.wait_until_stopped(5):raise RuntimeError('No test breakpoint')
        report['breakpoint_hit']=c.eval_sync('rip')[0]==address
        if not c.cmd_sync('bc 0x'+format(address,'x')):raise RuntimeError('Breakpoint removal failed')
        if not c.go() or not c.wait_until_running(3):raise RuntimeError('Test child resume failed before detach')
        report['detached']=c.detach();attached=not report['detached']
        if attached:raise RuntimeError('Detach failed')
        before=len(ticks);time.sleep(.3)
        report['heartbeat_after_detach']=len(ticks)>before and child.poll() is None
        # Close only the dedicated debugger selected by caller after detaching.
        c.session_pid=args.debugger_pid
        c.terminate_session()
        before=len(ticks);time.sleep(.5)
        report['heartbeat_after_debugger_close']=len(ticks)>before and child.poll() is None
        report['passed']=all(report.get(k) for k in ('breakpoint_hit','detached','heartbeat_after_detach','heartbeat_after_debugger_close'))
    finally:
        if attached:c.detach()
        c.detach_session()
        try:report['child_exit']=child.wait(timeout=25)
        except subprocess.TimeoutExpired:
            report['child_exit']='timeout; isolated child terminated'
            child.terminate();child.wait(timeout=5)
            report['passed']=False
        (BUILD/'lifecycle_result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)
    if not report.get('passed'):raise SystemExit(1)

if __name__=='__main__':main()
