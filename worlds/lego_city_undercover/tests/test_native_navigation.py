"""Execute the bounded UI eligibility instructions against synthetic inventory.

No game process is opened. Only the RIP data displacement is relocated to the
test's own bank pointer; the replacement instructions themselves are exercised.
"""
import ctypes
import platform
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from model_selection import NAVIGATION_PATCHES


@unittest.skipUnless(sys.platform=='win32' and platform.machine().lower() in ('amd64','x86_64'),
                     'Native instruction replay requires Windows x64')
class NativeNavigationTests(unittest.TestCase):
    def test_navigation_accepts_owned_or_found_at_word_boundaries(self):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong,ctypes.c_ulong]
        kernel.VirtualAlloc.restype=ctypes.c_void_p
        kernel.VirtualProtect.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong,ctypes.POINTER(ctypes.c_ulong)]
        kernel.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong]
        kernel.GetCurrentProcess.restype=ctypes.c_void_p
        kernel.FlushInstructionCache.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t]
        for block_index,(_,_,replacement) in enumerate(NAVIGATION_PATCHES):
            # Save nonvolatile registers, make rcx+rax refer to the model int16.
            prefix=bytes.fromhex('53 56 48 89 c8 31 c9')
            code=bytearray(prefix+replacement)
            code+=bytes.fromhex('89 f0' if block_index==0 else '89 d8')
            code+=bytes.fromhex('5e 5b c3')
            pointer_offset=(len(code)+7)&~7
            code+=b'\x90'*(pointer_offset-len(code))+b'\0'*8
            struct.pack_into('<i',code,len(prefix)+7,pointer_offset-(len(prefix)+11))
            memory=kernel.VirtualAlloc(None,4096,0x3000,4)
            if not memory:raise ctypes.WinError(ctypes.get_last_error())
            bank=(ctypes.c_ubyte*(0x80+1024))()
            struct.pack_into('<Q',code,pointer_offset,ctypes.addressof(bank))
            try:
                ctypes.memmove(memory,bytes(code),len(code));old=ctypes.c_ulong()
                self.assertTrue(kernel.VirtualProtect(memory,4096,0x20,ctypes.byref(old)))
                self.assertTrue(kernel.FlushInstructionCache(kernel.GetCurrentProcess(),memory,len(code)))
                eligible=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.POINTER(ctypes.c_short))(memory)
                for model in (0,7,31,32,63,64,270,291,1001,1023):
                    for found in (False,True):
                        for owned in (0,1):
                            ctypes.memset(bank,0,len(bank))
                            if found:bank[model//8]|=1<<(model%8)
                            bank[0x80+model]=owned
                            entry=ctypes.c_short(model)
                            with self.subTest(block=block_index,model=model,found=found,owned=owned):
                                self.assertEqual(bool(eligible(ctypes.byref(entry))),bool(found or owned))
            finally:kernel.VirtualFree(memory,0,0x8000)
