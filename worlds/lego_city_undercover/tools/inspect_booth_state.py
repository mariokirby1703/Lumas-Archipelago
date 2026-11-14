"""Bounded, read-only scan for exact RTTI-identified booth UI instances."""
import ctypes
import json
from pathlib import Path
import struct
import sys
import time

WORLD=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(WORLD/'bridge'))
from live_monitor import Session
from inventory_reader import pointer


class Region(ctypes.Structure):
    _fields_=[('base',ctypes.c_void_p),('allocation',ctypes.c_void_p),
              ('allocation_protect',ctypes.c_ulong),('size',ctypes.c_size_t),
              ('state',ctypes.c_ulong),('protect',ctypes.c_ulong),('type',ctypes.c_ulong)]


def inspect():
    session=Session();kernel=session.kernel;query=None
    try:
        kernel.VirtualQueryEx.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(Region),ctypes.c_size_t]
        kernel.VirtualQueryEx.restype=ctypes.c_size_t
        query=kernel.OpenProcess(0x410,False,session.pid)
        if not query:raise ctypes.WinError(ctypes.get_last_error())
        patterns={struct.pack('<Q',session.base+r):name for r,name in
                  ((0xc861b0,'booth_wheel'),(0xc86370,'shop_grid'),(0xc84c18,'shop_hud'))}
        regions=[];address=0x10000
        while address<0x7fffffffffff:
            region=Region()
            if not kernel.VirtualQueryEx(query,address,ctypes.byref(region),ctypes.sizeof(region)):break
            lo=region.base or address;address=lo+region.size
            if region.state==0x1000 and region.type==0x20000 and not region.protect&0x100 and region.protect&0xff in (4,8,0x40,0x80):
                regions.append((lo,region.size))
        anchors=[pointer(session.read,session.base+r) for r in (0x1c7d3e0,0x1c7cbb8,0x17ebd38)]
        # Prioritize live engine heaps over unrelated private graphics buffers.
        regions.sort(key=lambda r:(min(abs(r[0]-p) for p in anchors)//0x10000000,r[1]))
        buffer=ctypes.create_string_buffer(65536);count=ctypes.c_size_t()
        rows=[];scanned=0;started=time.monotonic();complete=True
        for lo,size in regions:
            for relative in range(((size-1)//len(buffer))*len(buffer),-1,-len(buffer)):
                address=lo+relative
                if time.monotonic()-started>20 or scanned>=8*1024**3:
                    complete=False;break
                length=min(len(buffer),lo+size-address)
                if not kernel.ReadProcessMemory(query,address,buffer,length,ctypes.byref(count)) or count.value!=length:continue
                data=buffer.raw[:length];scanned+=length
                for pattern,name in patterns.items():
                    offset=0
                    while (offset:=data.find(pattern,offset))>=0:
                        candidate=address+offset;offset+=8
                        if candidate%8:continue
                        try:
                            raw=session.read(candidate,0xa0 if name=='booth_wheel' else 0x440)
                            if raw[:8]!=pattern:continue
                            row=dict(kind=name,address=hex(candidate))
                            if name=='booth_wheel':
                                row.update(selected_button=hex(struct.unpack_from('<Q',raw,0x80)[0]))
                            elif name=='shop_hud':
                                # Interface at +0x38; method 0x25cd30 uses these fields.
                                raw=session.read(candidate+0x38+0x146c,0x30)
                                row.update(mode=struct.unpack_from('<i',raw)[0],state=struct.unpack_from('<i',raw,8)[0],
                                           category=struct.unpack_from('<h',raw,0x12)[0],selected_model=struct.unpack_from('<h',raw,0x26)[0])
                            else:
                                row.update(entry=struct.unpack_from('<i',raw,0x230)[0],mode=struct.unpack_from('<i',raw,0x420)[0],
                                           callback=hex(struct.unpack_from('<Q',raw,0x340)[0]))
                            rows.append(row)
                        except (OSError,RuntimeError,ValueError):pass
            if not complete:break
        return dict(pid=session.pid,scanned_mib=scanned//1048576,complete=complete,objects=rows)
    finally:
        if query:kernel.CloseHandle(query)
        session.close()


if __name__=='__main__':
    report=inspect();output=WORLD.parents[1]/'build/lego_city_undercover/booth_live_objects.json'
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
