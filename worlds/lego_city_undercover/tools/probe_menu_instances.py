"""Bounded read-only UI-class candidate search near the native frontend heap.

A matching vtable is only a candidate, not proof of a visible/focused menu.
Does not attach a debugger or change game memory.
"""
import ctypes
from collections import Counter
import json
from pathlib import Path
import struct
import sys
WORLD=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from live_monitor import Session

class Region(ctypes.Structure):
    _fields_=[('BaseAddress',ctypes.c_void_p),('AllocationBase',ctypes.c_void_p),
              ('AllocationProtect',ctypes.c_ulong),('PartitionId',ctypes.c_ushort),
              ('RegionSize',ctypes.c_size_t),('State',ctypes.c_ulong),
              ('Protect',ctypes.c_ulong),('Type',ctypes.c_ulong)]

def main():
    session=Session()
    report=dict(pid=session.pid,writes_enabled=False,scan_limit_bytes=128*1024*1024,
                bytes_read=0,candidates=[],visibility_verified=False)
    try:
        query=session.kernel.VirtualQueryEx
        query.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(Region),ctypes.c_size_t]
        query.restype=ctypes.c_size_t
        manager=struct.unpack('<Q',session.read(session.base+0x1c6b5d0,8))[0]
        if not manager:raise ValueError('Frontend manager absent')
        if struct.unpack('<Q',session.read(manager,8))[0]!=session.base+0xd0ce58:
            raise ValueError('Unknown frontend manager layout')
        start=(manager-0x4000000)&~0xffff;end=start+0x8000000
        needles={struct.pack('<Q',session.base+rva):name for rva,name in (
            (0xc6f4b8,'UIMenuButton'),(0xcf5c58,'GUI2Menu'),(0xcf6068,'GUI2MenuEntry'),
            (0xd98568,'LegoMenuItem'),(0xc6bb68,'LegoCityMenus'),(0xd96ac0,'GameFrontend'))}
        address=start
        while address<end and report['bytes_read']<report['scan_limit_bytes']:
            region=Region()
            if not query(session.handle,address,ctypes.byref(region),ctypes.sizeof(region)):break
            nextaddr=region.BaseAddress+region.RegionSize
            if nextaddr<=address:raise RuntimeError('Invalid memory-region progression')
            if region.State==0x1000 and region.Type==0x20000 and region.Protect in (4,8,0x40):
                for pos in range(max(address,region.BaseAddress),min(end,nextaddr),4096):
                    if report['bytes_read']>=report['scan_limit_bytes']:break
                    try:data=session.read(pos,min(4096,nextaddr-pos,end-pos))
                    except OSError:continue
                    report['bytes_read']+=len(data)
                    for needle,name in needles.items():
                        index=0
                        while (index:=data.find(needle,index))>=0:
                            candidate=pos+index;index+=8
                            if candidate%8==0 and len(report['candidates'])<1024:
                                report['candidates'].append(dict(address=hex(candidate),kind=name))
            address=nextaddr
        report['counts']=dict(Counter(r['kind'] for r in report['candidates']))
        output=WORLD.parents[1]/'build/lego_city_undercover/debugger/nearby_menu_candidates.json'
        output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(dict(bytes_read=report['bytes_read'],counts=report['counts'],writes_enabled=False),indent=2))
    finally:session.close()

if __name__=='__main__':main()
