"""Capture the EggmanMedal native pickup before it removes its own actor.

Host arms an exact ORC-validated actor in an attributed Game Land playthrough.
Gecko captures the native consumed event, never a score delta or disappearance.
The seed-owned 21-bit latch survives stage exit between host observations.
"""
import struct
from .capsule_refresh import PPC
from .gecko import inspect_c2
from .memory import MemoryUnavailable, valid_range
from .progression_hook import identity_tag

HOOK, ORIGINAL = 0x802F27C4, 0x7F83E378  # mr r3,r28; next calls hide and remove
VTABLE = 0x8077E714


def payload():
    a = PPC()
    a.d(37, 1, 1, -0x50)
    a.d(36, 0, 1, 16); a.emit(0x7C0802A6); a.d(36, 0, 1, 8)
    a.emit(0x7C000026); a.d(36, 0, 1, 12)
    registers = (3, 4, 5, 6, 7, 12)
    for i, r in enumerate(registers): a.d(36, r, 1, 20+i*4)
    a.emit(0x48000005); base = len(a.words)*4
    a.emit(0x7D8802A6); fix = len(a.words); a.d(14, 12, 12, 0)
    def equal(ra, rb):
        a.emit(0x7C000000 | ra << 16 | rb << 11); a.branch('end', 0x40820000)
    a.d(32, 6, 12, 0); a.d(11, 0, 6, 0); a.branch('end', 0x41820000)
    a.d(34, 6, 6, 0); a.d(32, 7, 12, 4); equal(6, 7)
    a.d(32, 6, 12, 8); equal(6, 28)
    a.d(32, 6, 28, 0); a.d(15, 7, 0, 0x8078); a.d(14, 7, 7, -0x18ec); equal(6, 7)
    for actor_offset, data_offset in ((0xc, 12), (0x64, 16), (0x34, 20)):
        a.d(32, 6, 28, actor_offset); a.d(32, 7, 12, data_offset); equal(6, 7)
    a.d(32, 5, 12, 16)
    a.d(32, 6, 5, 4); equal(6, 28)
    a.d(32, 6, 5, 8); a.d(32, 7, 12, 24); equal(6, 7)
    a.d(32, 5, 5, 12)
    a.d(32, 6, 5, 0x14); a.d(32, 7, 12, 28); equal(6, 7)
    a.d(32, 6, 12, 40); a.d(32, 7, 12, 32)
    a.emit(0x7CC63B78); a.d(36, 6, 12, 40)  # or r6,r6,r7
    a.label('end')
    for i, r in enumerate(registers): a.d(32, r, 1, 20+i*4)
    a.d(32, 0, 1, 12); a.emit(0x7C0FF120)
    a.d(32, 0, 1, 8); a.emit(0x7C0803A6)
    a.d(32, 0, 1, 16); a.d(14, 1, 1, 0x50); a.emit(ORIGINAL)
    a.branch('return')
    offset = len(a.words)*4; a.words[fix] |= (offset-base)&0xffff
    for _ in range(11): a.emit(0)
    a.label('return')
    if len(a.words)%2 == 0: a.emit(0x60000000)
    a.emit(0)
    return a.finish(), offset


def installed_data(memory):
    words, offset = payload()
    result = inspect_c2(memory, HOOK, ORIGINAL, {'egg_medal': words}, ((offset, 44),), 'Egg Medal')
    if not result['installed']: return None
    address = result['target'] + offset
    values = struct.unpack('>11I', memory.read_bytes(address, 44))
    if (any(v and not valid_range(v, 4) for v in (values[0], values[2], values[4], values[5], values[6]))
            or values[1] > 3 or values[7] >= 4096 or values[8] >= 1 << 21
            or values[8] and values[8] & (values[8]-1) or values[10] >= 1 << 21):
        raise MemoryUnavailable('unknown_revision: invalid Egg Medal capture data')
    return address


def observe(memory, snapshot, journal, slot):
    """Consume already captured events before changing the next armed actor."""
    address = installed_data(memory)
    if address is None: return
    chain = memory.resolve_flags_ptr()
    owner, index = struct.unpack('>2I', memory.read_bytes(address, 8))
    if (owner, index) != (chain[1], chain[2]) or memory.read_u32(address+36) != identity_tag(journal.identity): return
    from ..medals import MEDALS
    mask = memory.read_u32(address+40)
    selected = {name: code for name, code in slot['locations'].items() if name.endswith(' - Egg Medal')}
    rows = [r for r in MEDALS if mask & (1 << r['index']) and r['location_name'] in selected
            and selected[r['location_name']] not in journal.data['pickup_checks']]
    if rows:
        journal.record_pickups([{'kind': 'egg_medal', 'mission': r['mission_id'],
                                'instance_key': f"{r['mission_id']}:{r['object_id']}:{r['instance_index']}",
                                'provenance': 'PAL_802F27C4_native_pickup', 'stage_epoch': snapshot.stage_epoch}
                               for r in rows], {}, {selected[r['location_name']] for r in rows})
        import logging
        logging.getLogger('Client').info('Pickup detected: Egg Medals %s; Location queued: %s',
            [r['location_name'] for r in rows], [selected[r['location_name']] for r in rows])


def configure(memory, snapshot, journal):
    address = installed_data(memory)
    if address is None:
        return {'available': False, 'reason': 'Egg Medal hook not installed: check enabled code and Gecko RAM-table capacity; use the current compact export'}
    chain = memory.resolve_flags_ptr()
    stage = next(iter(snapshot.evidence.get('native_data', {}).get('stage_objects', [])), {})
    medals = stage.get('medals', ()) if snapshot.scene == 'gameplay' else ()
    row = medals[0] if len(medals) == 1 else None
    values = (chain[1], chain[2], row['actor'] if row else 0, row['actor_id'] if row else 0,
              row['wrapper'] if row else 0, row['manager'] if row else 0, row['record'] if row else 0,
              row['instance'] if row else 0, 1 << row['index'] if row else 0, identity_tag(journal.identity))
    old = struct.unpack('>10I', memory.read_bytes(address, 40))
    if old == values: return {'available': True, 'armed': bool(row)}
    # Actor zero disables capture during a multiword context change.
    if old[2]: memory.write_u32(address+8, 0, expected=old[2], operation='egg_medal_controls')
    if old[9] != values[9]:
        before = memory.read_u32(address+40)
        if before: memory.write_u32(address+40, 0, expected=before, operation='egg_medal_controls')
    for i, value in enumerate(values):
        if i == 2: continue
        before = memory.read_u32(address+i*4)
        if before != value: memory.write_u32(address+i*4, value, expected=before, operation='egg_medal_controls')
    if values[2]: memory.write_u32(address+8, values[2], expected=0, operation='egg_medal_controls')
    return {'available': True, 'armed': bool(row)}


def gecko_lines():
    words, _ = payload()
    return (['$AP PAL Egg Medal pickup capture', '20000000 534E4350', '28000004 00003850',
             '28000006 00000000', f'20{HOOK-0x80000000:06X} {ORIGINAL:08X}',
             f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}']
            + [f'{words[i]:08X} {words[i+1]:08X}' for i in range(0, len(words), 2)]
            + ['E0000000 80008000'])
