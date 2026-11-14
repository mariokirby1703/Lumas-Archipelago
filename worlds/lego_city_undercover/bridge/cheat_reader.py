"""Read the exact native cheat table and separate discovery/effect masks."""
import struct
from inventory_reader import pointer,cstring


def read_cheats(read,base):
    manager=pointer(read,base+0x11755F8)
    if not manager:return dict(status='not_initialized',records=[])
    table=pointer(read,manager);count=struct.unpack('<I',read(manager+8,4))[0]
    if not 0<count<=64:raise ValueError('Invalid cheat table count')
    found_bank=pointer(read,base+0x1C7E848);effect_bank=pointer(read,base+0x1C7E850)
    if not found_bank or not effect_bank:return dict(status='not_initialized',records=[])
    found=read(found_bank,8);effects=read(effect_bank,8)
    found_bits=struct.unpack('<Q',found)[0];effect_bits=struct.unpack('<Q',effects)[0];rows=[]
    for index in range(count):
        data=read(table+index*32,32);name=cstring(read,pointer(read,struct.unpack_from('<Q',data)[0]))
        rows.append(dict(index=index,native_name=name,found=bool(found_bits&(1<<index)),
                         effect_flag=bool(effect_bits&(1<<index))))
    if (pointer(read,base+0x11755F8)!=manager or pointer(read,manager)!=table or
        read(found_bank,8)!=found or read(effect_bank,8)!=effects):raise RuntimeError('Cheat state changed')
    return dict(status='read',records=rows,evidence='native table; 0x7f18c0 discovery + 0x7f19a0 effect')
