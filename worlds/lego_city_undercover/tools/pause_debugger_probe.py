"""Bounded x64dbg observation of the pinned game's native menu functions.

Uses a separate debugger Python environment. Never launches/restarts the game,
changes registers, calls engine functions or writes save/asset files. Software
breakpoints temporarily change instruction bytes and are removed in finally.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

WORLD=Path(__file__).resolve().parents[1]
ROOT=WORLD.parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
sys.path.insert(0,str(WORLD/'tools'))

TARGETS={0x797d0:'PauseDrawerConstruction',0x7a270:'PauseRenderCandidate',
         0x1f9830:'UIMenuButtonSelectable',0x556770:'GUI2MenuUpdateCandidate',
         0x1f9e60:'UIMenuButtonStateChange',0x1f8b50:'UIMenuPageTransition',
         0x61cc20:'MenuFlow2Update',0xa4bed0:'LegoMenuItemMethod6',
         0xa4c160:'LegoMenuItemMethod7',0xa4bc00:'LegoMenuItemMethod8'}


def clear_generated_tls_breakpoints(client,breakpoint_type):
    """Our dedicated debugger creates these one-shot DLL-entry stops on attach."""
    entries=client.get_breakpoints(breakpoint_type)
    if len(entries)>512:raise RuntimeError('Unexpected debugger breakpoint count')
    removed=[]
    for bp in entries:
        if bp.name.startswith('TLS Callback ') and bp.singleshoot:
            if not client.cmd_sync('bc 0x'+format(bp.addr,'x')):
                raise RuntimeError('Could not remove debugger-generated TLS breakpoint')
            removed.append(dict(address=hex(bp.addr),name=bp.name))
    return removed


def main():
    build=ROOT/'build/lego_city_undercover/debugger'
    if (build/'live_probes_disabled.json').exists():
        raise RuntimeError('Live probes disabled: user reported unresponsive menu after detach; process survival is insufficient')
    lifecycle=json.loads((build/'lifecycle_result.json').read_text())
    passive=json.loads((build/'passive_attach_result.json').read_text())
    if (not lifecycle.get('passed') or not passive.get('detached') or
            not passive.get('same_process_alive') or not passive.get('observed_entry_bytes_unchanged')):
        raise RuntimeError('Validated isolated lifecycle and passive live attachment required')
    _observe(passive['game_pid'])


def _observe(expected_pid):
    from x64dbg_automate import X64DbgClient
    from x64dbg_automate.models import BreakpointType
    from live_monitor import Session
    from inspect_game import inspect_pe
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--debugger-pid',type=int,required=True)
    parser.add_argument('--seconds',type=float,default=5)
    parser.add_argument('--stop-file',type=Path,help='Stop cleanly when this caller-owned signal file exists')
    args=parser.parse_args()
    if not 0<args.seconds<=180:parser.error('Observation must be 0..180 seconds')
    exe=(WORLD/'notes/gamefiles/LEGOLCUR_DX11.exe').read_bytes()
    digest=hashlib.sha256(exe).hexdigest()
    if digest!='624fed07274bbd105d1d571ecb97a290df6f6f0aff76898c516890da6d136f76':
        raise ValueError('Unsupported original executable')
    pe=inspect_pe(exe)
    debugger=ROOT/'build/lego_city_undercover/debugger/x64dbg/release/x64/x64dbg.exe'
    c=X64DbgClient(str(debugger));session=None;installed=[];attached=False
    report=dict(executable_sha256=digest,game_calls=False,save_writes=False,hits=[])
    out=ROOT/'build/lego_city_undercover/debugger/menu_probe.json'
    try:
        session=Session()  # independently checks the RUNNING executable hash
        if session.pid!=expected_pid:raise RuntimeError('Game restarted; repeat passive lifecycle validation')
        report.update(game_pid=session.pid,module_base=hex(session.base))
        c.attach_session(args.debugger_pid)
        if c.is_debugging():raise RuntimeError('Debugger already has a target; leave it unchanged')
        # Check entry bytes before attachment/breakpoint writes.
        for rva in TARGETS:
            section=next(s for s in pe['sections'] if s['rva']<=rva<s['rva']+s['raw_size'])
            offset=section['raw_offset']+rva-section['rva']
            if session.read(session.base+rva,16)!=exe[offset:offset+16]:
                raise ValueError('Unsupported/modified function '+hex(rva))
        if not c.attach(session.pid):raise RuntimeError('Attach failed')
        attached=True
        # Some debugger configurations resume automatically after attaching.
        if c.is_running():
            import psutil
            # Attach can select an already-suspended helper thread. Select a
            # CPU-active existing thread; never resume suspended game threads.
            threads=sorted(psutil.Process(session.pid).threads(),key=lambda t:t.user_time+t.system_time,reverse=True)
            for thread in threads[:8]:
                c.switch_thread(thread.id)
                if c.pause():break
            else:raise RuntimeError('Could not pause attached process')
        if not c.wait_until_stopped(5):raise RuntimeError('No initial attach stop')
        report['removed_generated_tls']=clear_generated_tls_breakpoints(c,BreakpointType.BpNormal)
        for rva,name in TARGETS.items():
            address=session.base+rva
            if not c.set_breakpoint(address,name,singleshoot=True):raise RuntimeError('Breakpoint rejected')
            installed.append(address)
        if not c.cmd_sync('run'):raise RuntimeError('Resume failed')
        print('ARMED: menu observation active; automatic detach after timeout',flush=True)
        report['status']='observing'
        out.write_text(json.dumps(report,indent=2)+'\n')
        deadline=time.monotonic()+args.seconds
        while time.monotonic()<deadline:
            if args.stop_file and args.stop_file.exists():break
            if not c.is_running():
                values={name:c.eval_sync(name)[0] for name in ('rip','rcx','rdx','r8','r9','rsp')}
                rva=values['rip']-session.base
                hit=dict(registers={k:hex(v) for k,v in values.items()},rva=hex(rva),name=TARGETS.get(rva,'other_stop'))
                if rva in TARGETS:
                    try:hit['stack']=c.read_memory(values['rsp'],128).hex()
                    except Exception as error:hit['stack_error']=str(error)
                    if values['rcx']:
                        try:hit['this_object']=c.read_memory(values['rcx'],0x220).hex()
                        except Exception as error:hit['this_error']=str(error)
                report['hits'].append(hit)
                out.write_text(json.dumps(report,indent=2)+'\n')
                print('HIT: '+hit['name']+' '+hit['rva'],flush=True)
                if rva not in TARGETS:break  # do not swallow unknown exceptions
                if not c.cmd_sync('run'):raise RuntimeError('Resume failed')
            time.sleep(.05)
    finally:
        if attached:
            if c.is_running():c.pause()
            for address in installed:c.cmd_sync('bc 0x'+format(address,'x'))
            clear_generated_tls_breakpoints(c,BreakpointType.BpNormal)
            # Detaching while stopped stranded the isolated heartbeat child.
            # Resume and confirm running BEFORE asking the debugger to detach.
            if not c.is_running():
                if not c.go() or not c.wait_until_running(3):
                    raise RuntimeError('Could not resume before detach; debugger left attached for recovery')
            report['detached']=c.detach()
            if not report['detached']:raise RuntimeError('Debugger detach failed; inspect running debugger')
        c.detach_session()
        if session:session.close()
        report['status']='detached' if report.get('detached') else 'not_attached'
        out.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))

if __name__=='__main__':main()
