"""Refresh Grand World Map locks through native PAL UI ownership routines.

The C2 runs at the void update's epilogue, after UI update and before the
original restoration of nonvolatile GPRs/FPRs. No host actor/handle mutations.
"""
from .capsule_refresh import PPC
from .gecko import inspect_c2
from .memory import MemoryUnavailable, valid_range

HOOK = 0x80266410
ORIGINAL = 0x396102E0


def payload():
    a = PPC()
    a.d(37, 1, 1, -0x60)
    a.emit(0x48000005); base = len(a.words)*4
    a.emit(0x7FA802A6)  # mflr r29 (outer PAL epilogue restores r29/LR)
    fix = len(a.words); a.d(14, 29, 29, 0)
    a.d(32, 3, 29, 0); a.emit(0x7C03D800); a.branch('end', 0x40820000)
    a.d(32, 3, 29, 8); a.d(34, 3, 3, 0); a.d(32, 0, 29, 12)
    a.emit(0x7C030000); a.branch('end', 0x40820000)
    a.d(32, 30, 29, 4); a.d(11, 0, 30, 1); a.branch('end', 0x41800000)
    a.d(11, 0, 30, 6); a.branch('end', 0x41810000)
    a.d(32, 0, 27, 0x10f0); a.d(11, 0, 0, 9); a.branch('end', 0x40820000)
    # Follow 802671AC's native unlock: queue the lock animation, then release
    # the actor's managed reference. Never host-zero +B4.
    a.emit(0x57DF1838)  # slwi r31,r30,3
    a.emit(0x7FFBFA14)  # add r31,r27,r31
    a.d(14, 31, 31, 0xb0)
    a.d(32, 0, 31, 4); a.d(11, 0, 0, 0); a.branch('done', 0x41820000)
    a.d(32, 3, 27, 0x90); a.mr(4, 31); a.call(0x805E7EE4)
    a.mr(3, 31); a.d(14, 4, 0, 0); a.call(0x805E9D80)
    # Terminal Velocity has no chain02..06 pair in the native initializer.
    a.d(11, 0, 30, 6); a.branch('done', 0x41820000)
    a.d(32, 0, 27, 0x110c); a.emit(0x54001838)  # slwi r0,r0,3
    a.d(32, 3, 27, 0x18c); a.emit(0x7C63002E)  # lwzx r3,r3,r0
    a.d(32, 12, 3, 8); a.d(32, 12, 12, 0xc0)
    a.emit(0x7D8903A6); a.emit(0x4E800421)
    a.d(36, 3, 1, 0x30)
    for address, hidden in ((0x80722ACE, 0), (0x80722ADB, 1)):
        a.d(14, 3, 1, 0x34); a.d(15, 4, 0, address >> 16); a.d(24, 4, 4, address & 0xffff)
        a.d(14, 5, 30, 1); a.emit(0x4CC63182)  # crclr 6 for sprintf varargs
        a.call(0x80379820)
        a.d(14, 3, 1, 0x30); a.d(14, 4, 1, 0x34); a.d(14, 5, 0, hidden)
        a.call(0x8026399C)
    a.label('done'); a.d(14, 0, 0, 0); a.d(36, 0, 29, 0)
    a.label('end'); a.d(14, 1, 1, 0x60); a.emit(ORIGINAL); a.branch('return')
    offset = len(a.words)*4; a.words[fix] |= (offset-base)&0xffff
    for _ in range(4): a.emit(0)
    a.label('return')
    if len(a.words)%2 == 0: a.emit(0x60000000)
    a.emit(0)
    return a.finish(), offset


def installed_data(memory):
    words, offset = payload()
    result = inspect_c2(memory, HOOK, ORIGINAL, {'grand_map_refresh': words}, ((offset, 16),), label='Grand World Map refresh')
    if not result['installed']: return None
    data = result['target'] + offset
    actor, zone, owner, index = (memory.read_u32(data+i*4) for i in range(4))
    if (actor and (not valid_range(actor,0x1374) or not owner or not zone)
            or owner and not valid_range(owner,1) or zone > 6 or index > 2):
        raise MemoryUnavailable('unknown_revision: invalid Grand World Map request')
    return data


def configure(memory, snapshot, permissions):
    if snapshot.scene != 'global_map': return {'available':False, 'reason':'not on Grand World Map'}
    from .native_read import read_actors
    context = snapshot.evidence['native_data']['stage_objects'][0]['context']
    actors = [p for p in read_actors(memory, context) if memory.read_u32(p) == 0x80777000]
    if len(actors) != 1: return {'available':False, 'reason':'Grand World Map actor not uniquely attributed'}
    actor = actors[0]
    data = installed_data(memory)
    if data is None:
        return {'available': False, 'reason': 'Update speed/White Boost Gecko group for Grand World Map refresh'}
    chain = memory.resolve_flags_ptr()
    if memory.read_u32(data):
        if (memory.read_u32(data) != actor or memory.read_u32(data+8) != chain[1]
                or memory.read_u32(data+12) != chain[2]):
            memory.write_u32(data,0,expected=memory.read_u32(data),operation='global_map_refresh')
        else: return {'available':True, 'pending_zone':memory.read_u32(data+4)}
    if memory.read_u32(actor+0x10f0) != 9:
        return {'available':True, 'reason':'waiting for interactive map state'}
    for zone in range(1, 7):
        if permissions.get(20+zone) and memory.read_u32(actor+0xb4+zone*8):
            memory.write_u32(data+4, zone, expected=memory.read_u32(data+4), operation='global_map_refresh')
            memory.write_u32(data+8, chain[1], expected=memory.read_u32(data+8), operation='global_map_refresh')
            memory.write_u32(data+12, chain[2], expected=memory.read_u32(data+12), operation='global_map_refresh')
            memory.write_u32(data, actor, expected=0, operation='global_map_refresh')
            return {'available': True, 'requested_zone': zone}
    return {'available': True}
