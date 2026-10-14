"""Two-line mailbox wire format; no RAM addresses or executable installation.

The future native publisher must acknowledge BOTH lines before the scheduler
commits an event. These helpers cannot establish font or render readiness.
"""
import struct
from .ap_hud_ticker import ascii_text

CAPACITY=128
SIZE=4+2*CAPACITY


def encode(generation,title,subtitle):
    if type(generation) is not int or not 0<generation<=0xfffffffe or generation&1:
        raise ValueError('published generation must be nonzero, even and u32')
    def line(text):
        raw=ascii_text(text).encode('ascii')
        if len(raw)>=CAPACITY:
            raise ValueError('fit text to verified glyph metrics before publication')
        return raw+b'\0'*(CAPACITY-len(raw))
    return struct.pack('>I',generation)+line(title)+line(subtitle)


def publication_writes(generation,title,subtitle):
    """Ordered offset/data pairs: odd marker, all bytes, even commit marker."""
    data=encode(generation,title,subtitle)
    return ((0,struct.pack('>I',generation-1)),(4,data[4:]),(0,data[:4]))


def acknowledged(expected,observed_before,observed_after,acknowledgement):
    return (type(expected) is int and 0<expected<=0xfffffffe and not expected&1
            and expected==observed_before==observed_after==acknowledgement)
