"""Hold a Windows kernel mutex for the entire native client's lifetime."""
import ctypes
import sys

class NativeClientLock:
    def __init__(self):self.handle=None;self.kernel=None
    def __enter__(self):
        if sys.platform!='win32':raise RuntimeError('Native LEGO client requires Windows')
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p]
        self.kernel.CreateMutexW.restype=ctypes.c_void_p
        self.kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        self.handle=self.kernel.CreateMutexW(None,False,'Local\\LCUNativeAPClient')
        error=ctypes.get_last_error()
        if not self.handle:raise ctypes.WinError(error)
        if error==183:
            self.__exit__(None,None,None)
            raise RuntimeError('A native LEGO AP client is already running. Close that client first.')
        return self
    def __exit__(self,*args):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None
