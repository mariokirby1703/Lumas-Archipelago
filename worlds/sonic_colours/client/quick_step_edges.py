import struct

from .capsule_refresh import PPC
from ..world_constants import load_data

HOOK = 0x8020D630
ORIGINAL = 0x2C1F0000
SUCCESS = 0x8020D73C


def program(control):
    a = PPC()

    def const(register, value):
        a.d(15, register, 0, value >> 16)
        a.d(24, register, register, value & 65535)

    def equal(left, right):
        a.emit(0x7C000000 | left << 16 | right << 11)
        a.branch('native', 0x40820000)

    const(12, control)
    a.d(32, 3, 12, 0)
    a.d(11, 0, 3, 1)
    a.branch('native', 0x40820000)
    a.d(32, 3, 28, 0)
    const(0, 0x8075A0F8)
    equal(3, 0)
    a.d(32, 12, 28, 0x28)
    a.d(11, 0, 12, 0)
    a.branch('native', 0x41820000)
    a.d(32, 3, 12, 0)
    const(0, 0x8075AEF8)
    equal(3, 0)
    a.d(32, 12, 12, 0x88)
    a.d(11, 0, 12, 0)
    a.branch('native', 0x41820000)
    a.d(32, 3, 12, 0)
    const(0, 0x8075AF40)
    equal(3, 0)

    # The input history stores one record per game frame, including stick axes.
    # A fresh side crossing counts even when the native flick flag is absent.
    a.d(32, 4, 12, 0xC)
    a.emit(0x5483007E)  # clrlwi r3,r4,1
    const(0, 0x3F800000)
    a.emit(0x7C030040)
    a.branch('button', 0x41810000)
    const(0, 0x3F000000)
    a.emit(0x7C030040)
    a.branch('button', 0x41800000)
    a.d(34, 5, 12, 0xA8)
    a.d(14, 5, 5, -1)
    a.emit(0x54A5063E)  # clrlwi r5,r5,24
    a.d(7, 5, 5, 0x48)
    a.emit(0x7CA56214)  # add r5,r5,r12
    a.d(32, 6, 5, 0xAC)
    a.emit(0x54C3007E)  # clrlwi r3,r6,1
    const(0, 0x3F800000)
    a.emit(0x7C030040)
    a.branch('button', 0x41810000)
    const(0, 0x3F000000)
    a.emit(0x7C030040)
    a.branch('edge', 0x41800000)
    a.emit(0x7CC62278)  # xor r6,r6,r4
    a.emit(0x74C08000)  # andis. r0,r6,0x8000
    a.branch('button', 0x41820000)
    a.label('edge')
    a.emit(0x54830FFE)  # srwi r3,r4,31
    a.d(26, 3, 3, 1)
    a.d(38, 3, 29, 0)  # native direction result: right=1, left=0
    a.branch('accepted')

    a.label('button')
    a.d(11, 0, 31, 0)
    a.branch('native', 0x41820000)
    a.d(32, 3, 12, 0x10)
    a.emit(0x5463007E)
    a.d(11, 0, 3, 0)
    a.branch('native', 0x41820000)
    const(0, 0x3F800000)
    a.emit(0x7C030040)
    a.branch('native', 0x41810000)
    a.label('accepted')
    a.d(14, 3, 0, 1)
    accepted = len(a.words)
    a.emit(0)
    a.label('native')
    a.emit(ORIGINAL)
    native = len(a.words)
    a.emit(0)
    return a.finish(), {accepted: SUCCESS, native: HOOK + 4}


def patches(control, occupied):
    from .native_events import scatter_mixed
    from .native_dol import branch
    sites = [site for site in load_data('quick_step_edge_sites.json')
             if not any(p < site['address'] + site.get('size', 12) and site['address'] < p + len(new)
                        for p, _, new in occupied)]
    words, returns = program(control)
    code, _ = scatter_mixed(words, sites, SUCCESS, pool=True, returns=returns)
    return code + [(HOOK, struct.pack('>I', ORIGINAL),
                    struct.pack('>I', branch(HOOK, code[0][0])))]
