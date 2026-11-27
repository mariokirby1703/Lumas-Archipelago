"""Typed read-only native MenuFlow2 page registry; not a pause-menu modifier.

The frontend registry may coexist with an in-game pause interface. Presence of
a page does not imply it is visible, focused, selectable, or safe to invoke.
"""
import struct
from inventory_reader import pointer

MANAGER_RVA=0x1C6B5D0
VTABLE_RVA=0xD0CE58


def parse_page_table(raw):
    if len(raw)!=16:raise ValueError('Incomplete menu array header')
    data,capacity,count=struct.unpack('<Qii',raw)
    if count!=44 or not count<=capacity<=128 or not data:
        raise ValueError('Unsupported MenuFlow2 page table')
    return data,count


def read_menu_flow(read,base):
    manager=pointer(read,base+MANAGER_RVA)
    if not manager:return dict(status='not_initialized',mutation_supported=False)
    if pointer(read,manager)!=base+VTABLE_RVA:raise ValueError('Unsupported MenuFlow2 object')
    states=read(manager+0x990,0x30);tables=[];guards=[]
    for offset in (0x970,0x980):
        header=read(manager+offset,16);data,count=parse_page_table(header)
        raw=read(data,count*8);entries=[]
        for index,address in enumerate(struct.unpack('<44Q',raw)):
            if not address:continue
            vtable=pointer(read,address)
            if not base<=vtable<base+0x2300000:raise ValueError('Unsupported native page vtable')
            entries.append(dict(index=index,address=hex(address),vtable_rva=hex(vtable-base)))
            guards.append((address,vtable))
        tables.append(dict(offset=hex(offset),entries=entries))
        guards.append((manager+offset,struct.unpack_from('<Q',header)[0]))
        if read(manager+offset,16)!=header or read(data,count*8)!=raw:
            raise RuntimeError('Menu page registry changed during read')
    if (pointer(read,base+MANAGER_RVA)!=manager or read(manager+0x990,0x30)!=states or
            any(pointer(read,address)!=value for address,value in guards)):
        raise RuntimeError('Menu context changed during read')
    return dict(status='read',manager=hex(manager),tables=tables,state_bytes=states.hex(),
                mutation_supported=False,visibility_verified=False,
                evidence='MenuFlow2 constructor 0x61c540; arrays 0x970/0x980 initialized at 0x61cdf0')
