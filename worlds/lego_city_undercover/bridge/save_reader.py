"""Read the native autosave controller; a request is not disk confirmation."""
import struct
from inventory_reader import pointer


def read_save_controller(read,base):
    stats=pointer(read,base+0x1c7a830)
    if not stats:return dict(status='not_initialized')
    raw=read(stats+0x3638+0x1c,8)
    return dict(status='read',timer=struct.unpack_from('<f',raw)[0],state=raw[4],
                enabled=bool(raw[5]),requested=bool(raw[7]),save_confirmed=False)
