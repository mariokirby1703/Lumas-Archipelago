"""Boot-time PAL renderer batch guard; exact Riivolution replacement only.

Original quad writer and its private copy helper occupy 164 bytes. Flush at
128 quads, reset the counter, then copy the next quad in native vertex order.
No extra arena and no host-side executable-memory writes are needed.
"""
import struct

ADDRESS=0x805ec6e0
SIZE=164
CAPACITY=128
BUFFER=0x808512e0
COUNTER=0x80853ae0
RENDERER=0x80853b00
ORIGINAL_HEX='9421ffe07c0802a63c60808590010024386312e0bfa100143fe080857c9d2378801f3ae01c0000507fc302147fc3f37848000049387e0014389d00284800003d387e0028389d003c48000031387e003c389d001448000025807f3ae038030001901f3ae0bba10014800100247c0803a6382100204e800020c0640000c0440004c024000cc004001080040008d0630000d0430004d023000cd0030010900300084e800020'

def replacement():
    words=[0x9421ffe0,0x7c0802a6,0x90010024,0xbfa10014,
           0x7c9d2378,0x3fe08085,0x801f3ae0,0x28000080,
           0x41800010, # blt -> destination calculation
           0x48000000|((0x805ec784-(ADDRESS+9*4))&0x3fffffc)|1,
           0x38000000,0x901f3ae0,0x1c000050,0x3bdf12e0,
           0x7fde0214,0x3cc00028,0x60c63c14,0x38e00004,
           0x54c8463e,0x7d1d4214,0x39200005,0x7d2903a6,
           0x80080000,0x901e0000,0x39080004,0x3bde0004,
           0x4200fff0,0x54c6403e,0x38e7ffff,0x2c070000,
           0x4082ffd0,0x807f3ae0,0x38030001,0x901f3ae0,
           0xbba10014,0x80010024,0x7c0803a6,0x38210020,
           0x4e800020,0x60000000,0x60000000]
    return struct.pack('>41I',*words)

def normalize(memory,data,base):
    if base<=ADDRESS and ADDRESS+SIZE<=base+len(data):
        off=ADDRESS-base
        if data[off:off+SIZE]==replacement():
            return data[:off]+bytes.fromhex(ORIGINAL_HEX)+data[off+SIZE:]
    return data
