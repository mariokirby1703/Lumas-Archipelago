"""Opt-in, hash-guarded activation of the manually verified N0CUT5 byte only."""
import ctypes
from ctypes import wintypes
import diagnose
from inventory_reader import pointer


def enable_cutscene_skip():
    processes=[p for p in diagnose.diagnose().get('processes',[]) if p['status']=='module_header_read']
    if len(processes)!=1:raise RuntimeError('No single supported game process')
    process=processes[0]
    kernel=diagnose.bind_kernel()
    kernel.WriteProcessMemory.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.c_void_p,
                                       ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)]
    kernel.WriteProcessMemory.restype=wintypes.BOOL
    handle=kernel.OpenProcess(0x1038,False,process['pid'])
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    try:
        read=lambda a,n:diagnose.read_memory(kernel,handle,a,n)
        base=int(process['module_base'],16)
        if read(base+0x7B7490,7)!=bytes.fromhex('889190010000c3'):
            raise ValueError('Skip setter signature mismatch')
        manager=pointer(read,base+0x17EBCF8)
        if not manager:raise ValueError('Cutscene manager unavailable')
        address=manager+0x190;before=read(address,1)
        if before not in (b'\0',b'\1'):raise ValueError('Unexpected skip flag')
        if pointer(read,base+0x17EBCF8)!=manager:raise RuntimeError('Manager changed')
        if before==b'\0':
            value=ctypes.c_ubyte(1);count=ctypes.c_size_t()
            if not kernel.WriteProcessMemory(handle,address,ctypes.byref(value),1,ctypes.byref(count)) or count.value!=1:
                raise ctypes.WinError(ctypes.get_last_error())
        if read(address,1)!=b'\1':raise RuntimeError('Skip flag did not persist')
        return dict(pid=process['pid'],before=before[0],after=1,only_written_field='allowcutskip')
    finally:kernel.CloseHandle(handle)
