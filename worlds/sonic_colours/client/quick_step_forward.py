import struct

from .capsule_refresh import PPC
from ..world_constants import load_data

HOOK=0x8020D638
ORIGINAL=0x7F83E378
SUCCESS=0x8020D73C


def program(control):
    a=PPC()
    def const(r,value):
        a.d(15,r,0,value>>16);a.d(24,r,r,value&65535)
    def equal(left,right):
        a.emit(0x7C000000|left<<16|right<<11);a.branch('native',0x40820000)
    const(12,control);a.d(32,3,12,0)
    a.d(11,0,3,1);a.branch('native',0x40820000)
    a.d(32,3,28,0);const(0,0x8075A0F8);equal(3,0)
    a.d(32,12,28,0x28);a.d(11,0,12,0);a.branch('native',0x41820000)
    a.d(32,3,12,0);const(0,0x8075AEF8);equal(3,0)
    a.d(32,12,12,0x88);a.d(11,0,12,0);a.branch('native',0x41820000)
    a.d(32,3,12,0);const(0,0x8075AF40);equal(3,0)
    # Native side-action and scene/form checks have already succeeded here.
    # Keep diagonal forward/back input from failing the later speed/heading checks.
    # No input bits, motion vectors or state queues are rewritten.
    a.d(32,3,12,0x10);a.emit(0x5463007E)
    a.d(11,0,3,0);a.branch('native',0x41820000)
    const(0,0x3F800000);a.emit(0x7C030040);a.branch('native',0x41810000)
    a.d(14,3,0,1);a.branch('accepted')
    a.label('native');a.emit(ORIGINAL)
    native_return=len(a.words);a.emit(0)
    a.label('accepted');a.emit(0)
    return a.finish(),{native_return:HOOK+4}


def patches(control,occupied):
    from .native_events import scatter_mixed
    from .native_dol import branch
    sites=[site for site in load_data('quick_step_forward_sites.json')
           if not any(p<site['address']+12 and site['address']<p+len(new) for p,_,new in occupied)]
    words,returns=program(control)
    code,_=scatter_mixed(words,sites,SUCCESS,returns=returns)
    return code+[(HOOK,struct.pack('>I',ORIGINAL),struct.pack('>I',branch(HOOK,code[0][0])))]
