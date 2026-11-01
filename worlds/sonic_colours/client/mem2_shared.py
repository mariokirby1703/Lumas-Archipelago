"""PID-bound Dolphin Wii shared memory, without creating a new mapping."""
import ctypes as c
from ctypes import wintypes as w

from .mem2_windows import dolphin_processes

MEM2_OFFSET = 0x02000000 + 0x00040000  # rounded MEM1, then locked L1 cache
MEM2_SIZE = 0x04000000
VIEW_SIZE = MEM2_OFFSET + MEM2_SIZE


class WindowsSharedMEM2:
    kind = 'verified Dolphin shared memory'

    def __init__(self, engine, *, writable=True):
        self.engine = engine
        self.handle = None
        self.base = 0
        self.writable = writable
        self.kernel = k = c.WinDLL('kernel32',use_last_error=True)
        signatures = {
            'OpenFileMappingW':([w.DWORD,w.BOOL,w.LPCWSTR],w.HANDLE),
            'MapViewOfFile':([w.HANDLE,w.DWORD,w.DWORD,w.DWORD,c.c_size_t],c.c_void_p),
            'UnmapViewOfFile':([c.c_void_p],w.BOOL),
            'CloseHandle':([w.HANDLE],w.BOOL),
            'GetCurrentProcess':([],w.HANDLE),
            'ReadProcessMemory':([w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)],w.BOOL),
            'WriteProcessMemory':([w.HANDLE,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)],w.BOOL),
        }
        for name,(args,result) in signatures.items():
            function = getattr(k,name)
            function.argtypes,function.restype = args,result
        processes = dolphin_processes()
        if len(processes) != 1:
            raise RuntimeError('shared MEM2 requires exactly one Dolphin process')
        self.pid = processes[0]['pid']
        from .native_dol import ARENA,plan
        from .native_events import SIZE,FRAME_FENCE
        self.frame_address = ARENA+len(plan()[1])-SIZE+FRAME_FENCE
        access = 0x04 | (0x02 if writable else 0)  # FILE_MAP_READ / FILE_MAP_WRITE
        self.handle = k.OpenFileMappingW(access,False,f'dolphin-emu.{self.pid}')
        if not self.handle:
            raise OSError(c.get_last_error(),'Dolphin shared mapping unavailable')
        try:
            self.base = k.MapViewOfFile(self.handle,access,0,0,VIEW_SIZE)
            if not self.base:
                raise OSError(c.get_last_error(),'Dolphin Wii shared view unavailable (requires standard RAM sizes)')
            self.validate_source()
        except Exception:
            self.close()
            raise

    def _read_offset(self, offset, size):
        if not self.base or not 0 <= offset < offset+size <= VIEW_SIZE:
            raise ValueError('shared RAM read outside verified view')
        buffer = c.create_string_buffer(size)
        transferred = c.c_size_t()
        if (not self.kernel.ReadProcessMemory(self.kernel.GetCurrentProcess(),self.base+offset,
                                             buffer,size,c.byref(transferred)) or transferred.value != size):
            raise OSError(c.get_last_error(),'Dolphin shared RAM read failed')
        return buffer.raw

    def validate_source(self):
        header = bytes(self.engine.read_bytes(0x80000000,8))
        if header[:6] != b'SNCP8P' or header[7] != 0 or self._read_offset(0,8) != header:
            raise RuntimeError('Dolphin shared MEM1 disc/revision differs from DME')
        for address,size in ((0x80004000,32),(0x80002FC0,64),(0x808F336C,4),
                             (0x808F34F8,4),(0x808F3628,4)):
            expected = bytes(self.engine.read_bytes(address,size))
            if address == 0x80002FC0 and expected[:8] != b'SCAPNAT1':
                raise RuntimeError('native AP signature required for shared MEM2')
            if self._read_offset(address-0x80000000,size) != expected:
                raise RuntimeError('Dolphin shared MEM1 identity/roots differ from DME')
        before = int.from_bytes(self.engine.read_bytes(self.frame_address,4),'big')
        shared = int.from_bytes(self._read_offset(self.frame_address-0x80000000,4),'big')
        after = int.from_bytes(self.engine.read_bytes(self.frame_address,4),'big')
        elapsed = (after-before)&0xFFFFFFFF
        if elapsed > 16 or (shared-before)&0xFFFFFFFF > elapsed:
            raise RuntimeError('Dolphin shared frame source differs from DME; retry after scene settles')

    def read(self, address, size):
        if not 0x90000000 <= address < address+size <= 0x94000000:
            raise ValueError('shared MEM2 access outside Wii RAM')
        return self._read_offset(MEM2_OFFSET+address-0x90000000,size)

    def write(self, address, data):
        if not self.writable or not self.base or not 0x90000000 <= address < address+len(data) <= 0x94000000:
            raise ValueError('shared MEM2 write outside verified writable view')
        transferred = c.c_size_t()
        buffer = c.create_string_buffer(data)
        target = self.base+MEM2_OFFSET+address-0x90000000
        if (not self.kernel.WriteProcessMemory(self.kernel.GetCurrentProcess(),target,buffer,len(data),
                                               c.byref(transferred)) or transferred.value != len(data)):
            raise OSError(c.get_last_error(),'Dolphin shared MEM2 write failed')

    def close(self):
        if self.base:
            self.kernel.UnmapViewOfFile(self.base)
            self.base = 0
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
