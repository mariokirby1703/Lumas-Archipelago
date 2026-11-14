"""Pinned, opt-in native item/save/policy RPC on the game window thread.

A returned command verifies memory only; native_save.py establishes disk proof.
"""
import ctypes
from ctypes import wintypes
from pathlib import Path
import struct
import time
import diagnose
from research_profile import symbol_hash

class NativePlayerBusy(RuntimeError):
    """The game rejected a command before mutation; retry a later snapshot."""


PACKET=struct.Struct('<16I')


def grant_model(pid,model,name,dll):
    return _command(pid,model,name,dll,1)


def request_save(pid,dll):
    result=_command(pid,0,'AUTOSAVE',dll,5)
    return dict(requested=bool(result['found']),save_confirmed=False)


def grant_currency(pid,kind,amount,dll,receipt_index,binding):
    allowed={'add_studs':(1000,10000,100000),'add_bricks':(100,250,1000,10000)}
    if kind not in allowed or type(amount) is not int or amount not in allowed[kind]:
        raise ValueError('Unbound currency package')
    if type(receipt_index) is not int or not 0<=receipt_index<0xffffffff or len(binding)!=16:
        raise ValueError('Invalid durable receipt identity')
    result=_command(pid,amount,kind.upper(),dll,6 if kind=='add_studs' else 7,receipt_index,binding)
    return dict(kind=kind,amount=amount,verified=bool(result['owned']),save_requested=bool(result['found']),save_confirmed=False)


def enforce_rewards(pid,policy,binding,dll):
    return _policy_command(pid,policy,binding,dll,8)


def preview_rewards(pid,policy,binding,dll):
    return _policy_command(pid,policy,binding,dll,9)


def grant_currency_batch(pid,deliveries,binding,dll):
    if not 0<len(deliveries)<=24 or len(binding)!=16:raise ValueError('Invalid currency batch')
    data=bytearray(320);struct.pack_into('<4I',data,0,0x4c435542,1,pid,len(deliveries));data[16:32]=binding
    previous=-1
    for i,row in enumerate(deliveries):
        plan=row['plan'];index=row['index'];kind=plan['kind'];amount=plan['amount']
        allowed={'add_studs':(1000,10000,100000),'add_bricks':(100,250,1000,10000)}
        if kind not in allowed or amount not in allowed[kind] or not previous<index<0xffffffff:raise ValueError('Invalid ordered currency batch')
        struct.pack_into('<3I',data,32+i*12,index,6 if kind=='add_studs' else 7,amount);previous=index
    result=_policy_command(pid,bytes(data),binding,dll,10)
    return dict(verified=True,credited=result['changes'],save_confirmed=False)


def _policy_command(pid,policy,binding,dll,opcode):
    from reward_policy import POLICY
    if len(policy)!=POLICY.size or len(binding)!=16:raise ValueError('Invalid native policy packet')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileMappingW.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.LPCWSTR]
    kernel.CreateFileMappingW.restype=wintypes.HANDLE
    kernel.MapViewOfFile.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,ctypes.c_size_t]
    kernel.MapViewOfFile.restype=ctypes.c_void_p
    kernel.UnmapViewOfFile.argtypes=[ctypes.c_void_p];kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    mapping=None;view=None
    try:
        mapping=kernel.CreateFileMappingW(wintypes.HANDLE(-1),None,4,0,len(policy),f'Local\\LCURewardPolicy_{pid}')
        existed=ctypes.get_last_error()==183
        if not mapping:raise ctypes.WinError(ctypes.get_last_error())
        if existed:raise RuntimeError('Another client owns the reward policy mapping')
        view=kernel.MapViewOfFile(mapping,0xf001f,0,0,len(policy))
        if not view:raise ctypes.WinError(ctypes.get_last_error())
        ctypes.memmove(view,policy,len(policy))
        result=_command(pid,0,'CURRENCY_BATCH' if opcode==10 else 'ENFORCE_POLICY',dll,opcode,0,binding)
        return dict(changes=result['found'],switch_requested=result['owned']==2,dry_run=opcode==9,save_confirmed=False)
    finally:
        if view:kernel.UnmapViewOfFile(view)
        if mapping:kernel.CloseHandle(mapping)


def probe_model(pid,model,name,dll):
    """Ask the native selection predicate on the game thread; no inventory writes."""
    result=_command(pid,model,name,dll,4)
    return dict(model=model,found=result['found'],availability=result['owned'])


def grant_ability(pid,name,dll):
    from research_profile import ABILITY_NAMES
    if name not in ABILITY_NAMES:raise ValueError('Unbound native ability: '+name)
    result=_command(pid,ABILITY_NAMES.index(name),name,dll,2)
    return dict(ability=name,enabled=result['found']==1,verified=result['found']==1,save_confirmed=False)


def grant_cheat(pid,index,name,dll):
    result=_command(pid,index,name,dll,3)
    return dict(cheat=name,found=result['found'],effect_flag=result['owned'],
                verified=result['owned']==1,save_confirmed=False)


def _command(pid,model,name,dll,opcode,receipt_index=0,binding=bytes(16)):
    from native_context_policy import NATIVE_OPCODES
    if opcode not in NATIVE_OPCODES:raise ValueError('Unknown native opcode')
    report=diagnose.diagnose()
    valid=[p for p in report.get('processes',[]) if p.get('status')=='module_header_read' and p['pid']==pid]
    if len(valid)!=1:raise RuntimeError('Pinned process identity no longer valid')
    dll=Path(dll).resolve()
    if not dll.is_file():raise RuntimeError('Build LCUItemBridge.dll first')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    user=ctypes.WinDLL('user32',use_last_error=True)
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user.EnumWindows.argtypes=[callback_type,wintypes.LPARAM]
    user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
    user.GetWindowThreadProcessId.restype=wintypes.DWORD
    user.IsWindowVisible.argtypes=[wintypes.HWND]
    windows=[]
    @callback_type
    def visit(hwnd,param):
        owner=wintypes.DWORD();thread=user.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value==pid and user.IsWindowVisible(hwnd):windows.append((hwnd,thread))
        return True
    user.EnumWindows(visit,0)
    threads={thread for _,thread in windows}
    if len(threads)!=1:raise RuntimeError('No unique game window thread')
    thread=next(iter(threads))
    kernel.CreateFileMappingW.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.LPCWSTR]
    kernel.CreateFileMappingW.restype=wintypes.HANDLE
    kernel.MapViewOfFile.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,ctypes.c_size_t]
    kernel.MapViewOfFile.restype=ctypes.c_void_p
    kernel.LoadLibraryExW.argtypes=[wintypes.LPCWSTR,wintypes.HANDLE,wintypes.DWORD]
    kernel.LoadLibraryExW.restype=wintypes.HMODULE
    kernel.GetProcAddress.argtypes=[wintypes.HMODULE,ctypes.c_char_p];kernel.GetProcAddress.restype=ctypes.c_void_p
    kernel.UnmapViewOfFile.argtypes=[ctypes.c_void_p];kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.FreeLibrary.argtypes=[wintypes.HMODULE]
    user.SetWindowsHookExW.argtypes=[ctypes.c_int,ctypes.c_void_p,wintypes.HMODULE,wintypes.DWORD]
    user.SetWindowsHookExW.restype=wintypes.HANDLE
    user.UnhookWindowsHookEx.argtypes=[wintypes.HANDLE]
    user.PostThreadMessageW.argtypes=[wintypes.DWORD,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    mapping=None;view=None;library=None;hook=None
    try:
        mapping=kernel.CreateFileMappingW(wintypes.HANDLE(-1),None,4,0,PACKET.size,f'Local\\LCUItemBridge2_{pid}')
        existed=ctypes.get_last_error()==183
        if not mapping:raise ctypes.WinError(ctypes.get_last_error())
        if existed:raise RuntimeError('Another model command owns this process mapping')
        view=kernel.MapViewOfFile(mapping,0xf001f,0,0,PACKET.size)
        if not view:raise ctypes.WinError(ctypes.get_last_error())
        # Initial state is idle. Publish pending only after the hook is installed.
        packet=PACKET.pack(0x4c435549,2,0,opcode,pid,thread,0,model,symbol_hash(name),0,0,
                           receipt_index,*struct.unpack('<4I',binding))
        ctypes.memmove(view,packet,len(packet))
        library=kernel.LoadLibraryExW(str(dll),None,1)  # DONT_RESOLVE_DLL_REFERENCES in host
        if not library:raise ctypes.WinError(ctypes.get_last_error())
        entry=kernel.GetProcAddress(library,b'ItemBridgeHook')
        if not entry:raise RuntimeError('Missing ItemBridgeHook export')
        hook=user.SetWindowsHookExW(3,entry,library,thread)
        if not hook:raise ctypes.WinError(ctypes.get_last_error())
        ctypes.c_long.from_address(view+8).value=1
        if not user.PostThreadMessageW(thread,0,0,0):raise ctypes.WinError(ctypes.get_last_error())
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            result=PACKET.unpack(ctypes.string_at(view,PACKET.size))
            if result[2] in (3,4):
                if result[2]!=3:
                    if result[6]==3:raise NativePlayerBusy('player is busy or not alive')
                    reasons={1:'native signature mismatch',2:'player is not loaded',3:'player is busy or not alive',
                        4:'native managers are not initialized',5:'unsupported native table/profile layout',
                        6:'command identity mismatch',7:'native effect verification failed',8:'native call faulted; inspect outcome before retry',
                        9:'unbound index or package',10:'unexpected booth navigation code',11:'native autosave is disabled',
                        12:'currency balance would overflow',13:'native save belongs to another AP binding',
                        14:'native autosave is busy',15:'reward policy mapping unavailable',16:'police lobby re-entry phase is unsupported; exit not triggered'}
                    raise RuntimeError(f"Native command rejected ({result[6]}): {reasons.get(result[6],'unknown native error')}")
                return dict(model=model,found=result[9],owned=result[10],verified=bool(result[10]),save_confirmed=False)
            time.sleep(.01)
        raise RuntimeError(f'Native command {opcode} ({name}) timed out; outcome uncertain, inspect memory before retry')
    finally:
        if hook:user.UnhookWindowsHookEx(hook)
        if library:kernel.FreeLibrary(library)
        if view:kernel.UnmapViewOfFile(view)
        if mapping:kernel.CloseHandle(mapping)


def trigger_station_exit(pid,dll):
    """Invoke only a pinned nearby police station exterior/lift door transition."""
    result=_command(pid,0,'STATION_EXIT',dll,12)
    return bool(result['found'])


def open_lobby_lift(pid,dll):
    """Open the existing arrival lift animation in the first lobby visit only."""
    return bool(_command(pid,0,'OPEN_LOBBY_LIFT',dll,13)['found'])
