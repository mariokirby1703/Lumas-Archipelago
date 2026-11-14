"""Replay the real shop guard instructions in isolated synthetic memory only."""
import ctypes
from pathlib import Path
import platform
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from purchase_gate import build_blocks,SITES,MASK_OFFSET,header

@unittest.skipUnless(sys.platform=='win32' and platform.machine().lower() in ('amd64','x86_64'),'Windows x64')
class ShopGuardTests(unittest.TestCase):
    def setUp(self):
        self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        self.k.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong,ctypes.c_ulong]
        self.k.VirtualAlloc.restype=ctypes.c_void_p
        self.k.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_ulong]
        self.base=self.k.VirtualAlloc(None,0x2100000,0x3000,0x40)
        if not self.base:raise ctypes.WinError(ctypes.get_last_error())
        self.block=self.base+0x2000000
        for offset,data in build_blocks(self.base,self.block):ctypes.memmove(self.block+offset,data,len(data))
        self.shop=ctypes.create_string_buffer(0x500)
        self.entries=ctypes.create_string_buffer(44*4)
        ctypes.c_uint64.from_address(self.base+0x11827b8).value=ctypes.addressof(self.entries)
        ctypes.c_uint16.from_address(self.base+0x11827c2).value=4
        ctypes.c_int32.from_buffer(self.shop,0x230).value=0
        # Original purchase continuation unwinds the replayed native prologue.
        self.write(0x264e78,'48 83 c4 50 5f 5e 5d b8 01 00 00 00 c3')
        self.write(0x265ea1,'b8 01 00 00 00 c3')
        self.write(0x265b65,'31 c0 c3')
        self.write(0x26613f,'44 89 c8 c3')
    def tearDown(self):self.k.VirtualFree(self.base,0,0x8000)
    def write(self,offset,data):
        value=bytes.fromhex(data) if isinstance(data,str) else data
        ctypes.memmove(self.base+offset,value,len(value))
    def mask(self,model):
        ctypes.memset(self.block+MASK_OFFSET,0,128)
        ctypes.c_ubyte.from_address(self.block+MASK_OFFSET+model//8).value=1<<(model%8)
    def invoke_ui(self,offset,model,owned,found=1):
        # Keep all Windows nonvolatile registers intact; reserve call shadow space.
        prefix=bytes.fromhex('53 56 57 41 54 41 55 41 56 48 83 ec 28 48 89 cb 41 89 d4 45 89 c5 89 d6 44 89 cf 45 89 ce')
        call=bytes.fromhex('48 b8')+struct.pack('<Q',self.block+offset)+bytes.fromhex('ff d0')
        suffix=bytes.fromhex('48 83 c4 28 41 5e 41 5d 41 5c 5f 5e 5b c3')
        self.write(0x2050000,prefix+call+suffix)
        fn=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int)(self.base+0x2050000)
        return fn(ctypes.addressof(self.shop),model,owned,found)
    def test_purchase_blocks_managed_models_before_original(self):
        fn=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p)(self.block)
        for model in (0,7,31,32,63,64,270,291,1001):
            ctypes.c_short.from_buffer(self.entries).value=model
            self.mask(model)
            self.assertEqual(fn(ctypes.addressof(self.shop)),0)
            ctypes.memset(self.block+MASK_OFFSET,0,128)
            self.assertEqual(fn(ctypes.addressof(self.shop)),1)
        for index in (-1,4):
            ctypes.c_int32.from_buffer(self.shop,0x230).value=index
            self.assertEqual(fn(ctypes.addressof(self.shop)),1)
    def test_ui_hides_buy_without_faking_ownership(self):
        for model in (0,31,32,270,291,1001):
            self.mask(model)
            self.assertEqual(self.invoke_ui(0x140,model,0),1)
            self.assertEqual(self.invoke_ui(0x240,model,0),0)
            self.assertEqual(self.invoke_ui(0x240,model,1),1)
            ctypes.memset(self.block+MASK_OFFSET,0,128)
            self.assertEqual(self.invoke_ui(0x140,model,0),0)
            self.assertEqual(self.invoke_ui(0x240,model,0),1)
    def test_initial_hud_callback_hides_only_unowned_managed_purchase(self):
        self.write(0x265ea1,'44 89 f0 c3')
        self.mask(270)
        self.assertEqual(self.invoke_ui(0x140,270,0),0)
        self.assertEqual(self.invoke_ui(0x140,270,1),1)
    def test_custom_characters_keep_native_ui(self):
        self.mask(270);ctypes.c_int32.from_buffer(self.shop,0x420).value=6
        self.assertEqual(self.invoke_ui(0x140,270,0),0)
        self.assertEqual(self.invoke_ui(0x240,270,0),1)
    def test_header_relocations_match_builder(self):
        import re
        source=header()
        for base,block in ((0x140000000,0x180000000),(0x7ff600000000,0x7ff610000000),
                           (0x7ff600000000,0x7ff5f0000000)):
            for i,(offset,expected) in enumerate(build_blocks(base,block)):
                values=re.search(r'shop_code_'+str(i)+r'\[\]=\{([^}]+)',source).group(1)
                data=bytearray(map(int,values.split(',')))
                body=source.split('static void RelocateShop'+str(i))[1].split('\n}')[0]
                for typ,expr,pos,size in re.findall(r'std::(uint64_t|int32_t)>\((.*?)\);std::memcpy\(p\+(\d+),&v,(\d+)\)',body):
                    expr=re.sub(r'static_cast<long long>\((base|block)\)',r'\1',expr).replace('LL','')
                    value=eval(expr,{'__builtins__':{}},{'base':base,'block':block})
                    struct.pack_into('<Q' if typ=='uint64_t' else '<i',data,int(pos),value)
                self.assertEqual(bytes(data),expected)

@unittest.skipUnless(sys.platform=='win32' and platform.machine().lower() in ('amd64','x86_64'),'Windows x64')
class CategoryGuardTests(unittest.TestCase):
    write=ShopGuardTests.write
    tearDown=ShopGuardTests.tearDown
    def setUp(self):
        ShopGuardTests.setUp(self)
        self.flags=self.base+0x2040000;self.alternate=self.base+0x2040100;self.bank=self.base+0x2041000
        ctypes.c_uint64.from_address(self.base+0x17ebfc8).value=self.flags
        ctypes.c_uint64.from_address(self.base+0x17ebfd0).value=self.alternate
        ctypes.c_uint64.from_address(self.base+0x1c7cbb8).value=self.bank
        for i,model in enumerate((276,442,1001,1002)):
            ctypes.c_short.from_buffer(self.entries,i*44).value=model
            self.entries[i*44+0x16]=bytes([8]);self.entries[i*44+0x17]=bytes([8 if i!=1 else 9])
        self.query=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_int,ctypes.c_int)(self.block+0x500)
    def test_owned_diver_opens_category_without_marking_found(self):
        before=ctypes.string_at(self.flags,12)
        self.assertEqual(self.query(8,1),0)
        ctypes.c_ubyte.from_address(self.bank+0x80+276).value=1
        self.assertEqual(self.query(8,1),1)
        self.assertEqual(self.query(8,0),1)
        self.assertEqual(self.query(9,1),0)
        self.assertEqual(ctypes.string_at(self.flags,12),before)
        self.assertEqual(ctypes.string_at(self.bank,128),bytes(128))
    def test_native_category_flags_and_model_bounds(self):
        ctypes.c_ubyte.from_address(self.flags+9).value=1
        self.assertEqual(self.query(9,1),1)
        self.assertEqual(self.query(9,0),0)
        ctypes.c_ubyte.from_address(self.alternate+9).value=1
        self.assertEqual(self.query(9,0),1)
        ctypes.c_ubyte.from_address(self.bank+0x80+1002).value=1
        self.assertEqual(self.query(8,1),0)
        ctypes.c_ubyte.from_address(self.bank+0x80+1001).value=1
        self.assertEqual(self.query(8,1),1)
