"""Choose the locked White capsule model before allocating its graphics."""
import struct
from functools import lru_cache

from .capsule_refresh import PPC
from ..world_constants import load_data

HOOK = 0x800D3C84
ORIGINAL = 0x2C1D0000
GHOST = 0x800D3CA4


def program(control):
    a = PPC()
    exits = {}
    a.d(37,1,1,-0x30)
    a.d(36,0,1,8)
    for r in range(9,13):a.d(36,r,1,12+(r-9)*4)
    a.emit(0x7C0902A6);a.d(36,0,1,0x20)
    # r30 is the capsule being constructed by the original PAL function.
    a.d(34,0,30,0x148);a.d(11,0,0,0);a.branch('allow',0x40820000)
    a.d(34,0,30,0x14A);a.d(11,0,0,0);a.branch('allow',0x40820000)
    a.d(32,0,30,0x114);a.d(11,0,0,-1);a.branch('allow',0x40820000)
    a.d(15,9,0,control>>16);a.d(24,9,9,control&65535)
    a.d(32,10,9,0);a.d(11,0,10,0);a.branch('deny',0x41820000)
    a.d(34,10,10,0);a.d(32,0,9,4)
    a.emit(0x7C0A0000);a.branch('deny',0x40820000)
    a.d(32,10,9,8);a.d(28,10,10,1);a.branch('allow',0x40820000)

    def restore():
        a.d(32,0,1,0x20);a.emit(0x7C0903A6)
        for r in range(9,13):a.d(32,r,1,12+(r-9)*4)
        a.d(32,0,1,8);a.d(14,1,1,0x30)

    a.label('deny');restore()
    # The original ghost path registers the locked lifecycle and omits the
    # pickup body. It also respects capsules hidden by native stage events.
    exits[len(a.words)] = GHOST;a.emit(0)
    a.label('allow');restore();a.emit(ORIGINAL);a.emit(0)
    return a.finish(), exits


def patches(control, occupied):
    from .native_dol import branch
    from .red_ring_spawn import scatter
    sites = [site for site in load_data('red_ring_spawn_sites.json')
             if not any(a < site['address']+8 and site['address'] < a+len(new)
                        for a,old,new in occupied)]
    words,exits = program(control)
    result = scatter(words,sites,HOOK+4,exits)
    return result+[(HOOK,struct.pack('>I',ORIGINAL),struct.pack('>I',branch(HOOK,result[0][0])))]


@lru_cache(maxsize=1)
def planned_patches():
    from .native_dol import plan
    base=plan(include_boot_guards=False)
    from . import capsule_refresh
    hook=next(row for row in base[3] if row['hook']==capsule_refresh.HOOK)
    control=hook['target']+capsule_refresh.data_offset(capsule_refresh.payload_words(
        compact_abi=True,epilogue_abi=True,cache_permissions=True))
    return patches(control,base[0])
