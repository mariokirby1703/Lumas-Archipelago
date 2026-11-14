"""Replay category UI count eligibility without changing discovery flags."""
import ctypes
from pathlib import Path
import platform
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from category_selection import COUNTER_RVA,COUNTER_PATCHED,LABEL_RVA,LABEL_PATCHED

@unittest.skipUnless(sys.platform=='win32' and platform.machine().lower() in ('amd64','x86_64'),'Windows x64')
class CategoryCounterTests(unittest.TestCase):
    def test_counter_accepts_discovered_or_owned_and_never_writes_inventory(self):
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong,ctypes.c_ulong]
        k.VirtualAlloc.restype=ctypes.c_void_p
        k.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong]
        memory=k.VirtualAlloc(None,4096,0x3000,0x40)
        if not memory:raise ctypes.WinError(ctypes.get_last_error())
        try:
            # RCX points to an entry's int16 model, RDX to the native bank.
            prefix=bytes.fromhex('49 89 d1 31 d2')
            code=bytearray(prefix+COUNTER_PATCHED+bytes.fromhex('0f 92 c0 0f b6 c0 c3'))
            target=len(code);code+=bytes.fromhex('b8 01 00 00 00 c3')
            struct.pack_into('<i',code,len(prefix)+15,target-(len(prefix)+19))
            ctypes.memmove(memory,bytes(code),len(code))
            query=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.POINTER(ctypes.c_short),ctypes.c_void_p)(memory)
            bank=ctypes.create_string_buffer(0x480)
            for model in (0,7,31,32,63,64,244,276,442,1001):
                for found in (False,True):
                    for owned in (False,True):
                        ctypes.memset(bank,0,len(bank))
                        if found:ctypes.c_ubyte.from_buffer(bank,model//8).value=1<<(model%8)
                        ctypes.c_ubyte.from_buffer(bank,0x80+model).value=int(owned)
                        before=bank.raw;entry=ctypes.c_short(model)
                        with self.subTest(model=model,found=found,owned=owned):
                            self.assertEqual(query(ctypes.byref(entry),ctypes.addressof(bank)),int(found or owned))
                            self.assertEqual(bank.raw,before)
        finally:k.VirtualFree(memory,0,0x8000)
    def test_mode3_label_reads_the_union_count(self):
        displacement=struct.unpack_from('<i',LABEL_PATCHED,3)[0]
        self.assertEqual(LABEL_RVA+7+displacement,0x183fc58)
        # The original downstream conditional increment remains untouched.
        self.assertEqual(len(COUNTER_PATCHED),0x2654a8-COUNTER_RVA)
