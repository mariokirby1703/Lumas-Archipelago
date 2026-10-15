"""First-run Dolphin selection and graceful single-instance game startup."""
import logging
import os
from pathlib import Path
import subprocess
import time

logger=logging.getLogger(__name__)


def select_executable(group,explicit=None,gui=True):
    first_setup=not vars(group).get('dolphin_path')
    configured=explicit or str(vars(group).get('dolphin_path',''))
    if not configured or not Path(configured).is_file():
        if not gui:
            raise ValueError('Select Dolphin once in the GUI or supply --dolphin PATH')
        from Utils import open_filename
        configured=open_filename('Select your Dolphin emulator executable',
                                 [('Dolphin executable',['.exe'] if os.name=='nt' else [''])],
                                 configured or 'Dolphin.exe')
        if not configured:return None
    path=Path(configured).expanduser().resolve()
    if not path.is_file() or os.name=='nt' and path.suffix.lower()!='.exe':
        raise ValueError('Select the Dolphin executable, not its installation folder')
    group.dolphin_path=type(group.dolphin_path)(str(path))
    if first_setup and hasattr(group,'auto_start'):group.auto_start=True
    from settings import get_settings
    get_settings().save()
    return path


def running_processes():
    if os.name=='nt':
        from .mem2_windows import dolphin_processes
        return dolphin_processes()
    # Do not assume a desktop emulator is absent on other platforms.
    result=subprocess.run(['ps','-A','-o','pid=,comm='],capture_output=True,text=True,check=True)
    names={'dolphin','dolphin-emu','dolphinqt2','dolphinwx'}
    return [{'pid':int(line.split(None,1)[0]),'executable':line.split(None,1)[1]}
            for line in result.stdout.splitlines() if len(line.split(None,1))==2
            and Path(line.split(None,1)[1]).name.lower() in names]


def request_close(pid):
    """Ask the existing Qt main window to exit, preserving its confirmation UI."""
    if os.name!='nt':
        raise ValueError('Close Dolphin before opening the patch on this platform.')
    import ctypes as c
    from ctypes import wintypes as w
    user=c.WinDLL('user32',use_last_error=True)
    callback_type=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    user.EnumWindows.argtypes=[callback_type,w.LPARAM]
    user.EnumWindows.restype=w.BOOL
    user.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)]
    user.IsWindowVisible.argtypes=[w.HWND]
    user.GetAncestor.argtypes=[w.HWND,w.UINT];user.GetAncestor.restype=w.HWND
    user.PostMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
    user.PostMessageW.restype=w.BOOL
    user.SetForegroundWindow.argtypes=[w.HWND]
    user.ShowWindowAsync.argtypes=[w.HWND,c.c_int]
    windows=set()
    @callback_type
    def visit(hwnd,param):
        owner=w.DWORD()
        user.GetWindowThreadProcessId(hwnd,c.byref(owner))
        if owner.value==pid and user.IsWindowVisible(hwnd):
            # Render windows and modal dialogs can be owned by a hidden main
            # window. Close that root owner rather than just the render view.
            root=user.GetAncestor(hwnd,3)  # GA_ROOTOWNER
            root_pid=w.DWORD()
            if root:
                user.GetWindowThreadProcessId(root,c.byref(root_pid))
                if root_pid.value==pid:windows.add(root)
        return True
    if not user.EnumWindows(visit,0):raise c.WinError(c.get_last_error())
    if len(windows)!=1:
        raise ValueError('Dolphin main window could not be identified safely. Close Dolphin and open the patch again.')
    hwnd=next(iter(windows))
    user.ShowWindowAsync(hwnd,9)  # restore so native stop/exit confirmation is visible
    user.SetForegroundWindow(hwnd)
    if not user.PostMessageW(hwnd,0x10,0,0):raise c.WinError(c.get_last_error())  # WM_CLOSE


def close_existing(pid,timeout=60):
    logger.info('Restarting Dolphin with the patched ISO. Confirm any Dolphin stop/exit dialog to continue.')
    request_close(pid)
    deadline=time.monotonic()+timeout
    while True:
        processes=running_processes()
        if not processes:return
        if any(p['pid']!=pid for p in processes):
            raise ValueError('Another Dolphin instance appeared during restart; automatic startup cancelled.')
        if time.monotonic()>=deadline:
            raise ValueError('Dolphin has not closed. Confirm its stop/exit dialog, then open the patch again. No process was forcibly terminated.')
        time.sleep(.2)


def start_or_reuse(executable,iso):
    processes=running_processes()
    if len(processes)>1:
        raise ValueError('Multiple Dolphin instances are running. Keep only one for AP memory attribution.')
    if processes:
        close_existing(processes[0]['pid'])
        if running_processes():
            raise ValueError('Dolphin appeared before startup; refusing to open a second instance.')
    flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    process=subprocess.Popen([str(executable),'--exec',str(iso)],**flags)
    return {'started':True,'reused':False,'restarted':bool(processes),'pid':process.pid,'iso':str(iso)}


