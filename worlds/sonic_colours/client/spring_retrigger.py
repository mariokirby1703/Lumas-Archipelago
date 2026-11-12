import struct

from .capsule_refresh import PPC
from ..world_constants import load_data

HOOK = 0x800CE4C8
ORIGINAL = 0x9421FFD0
SPRING_STATE = 0x8075E8AC
MIN_LAUNCH_TIME = 0.05


def program():
    a = PPC()
    def const(register, value):
        a.d(15, register, 0, value >> 16)
        a.d(24, register, register, value & 65535)
    def restore():
        a.d(32, 0, 1, 20); a.emit(0x7C0FF120)
        a.d(32, 6, 1, 12); a.d(32, 7, 1, 16)
        a.d(32, 0, 1, 8); a.d(14, 1, 1, 0x20)
    a.d(37, 1, 1, -0x20)
    a.d(36, 0, 1, 8); a.d(36, 6, 1, 12); a.d(36, 7, 1, 16)
    a.emit(0x7C000026); a.d(36, 0, 1, 20)
    a.d(32, 6, 3, 0); const(7, SPRING_STATE)
    a.emit(0x7C063800); a.branch('allow', 0x40820000)
    a.d(32, 6, 3, 8); a.d(11, 0, 6, 18); a.branch('allow', 0x40820000)
    a.d(32, 6, 3, 12); a.d(11, 0, 6, 1); a.branch('allow', 0x40820000)
    a.d(32, 6, 5, 4); a.d(11, 0, 6, 0x6000); a.branch('allow', 0x40820000)
    # Positive float bits have the same order as their values. Negative,
    # nonfinite and stale timers fall through to the original handler.
    a.d(32, 6, 3, 0x24)
    const(7, struct.unpack('>I', struct.pack('>f', MIN_LAUNCH_TIME))[0])
    a.emit(0x7C063840); a.branch('allow', 0x40800000)
    a.d(14, 0, 0, 1); a.d(38, 0, 5, 0x38)
    restore()
    a.d(14, 3, 0, 1); a.emit(0x4E800020)
    a.label('allow')
    restore()
    a.emit(ORIGINAL); a.emit(0)
    return a.finish()


def patches(occupied):
    from .native_events import scatter_mixed
    from .native_dol import branch
    sites = [site for site in load_data('native_event_sites.json')
             if not any(address < site['address'] + 12 and site['address'] < address + len(new)
                        for address, _, new in occupied)]
    if not sites:
        raise ValueError('No audited padding for Spring retrigger guard')
    code, _ = scatter_mixed(program(), sites, HOOK + 4)
    return code + [(HOOK, struct.pack('>I', ORIGINAL),
                    struct.pack('>I', branch(HOOK, code[0][0])))]
