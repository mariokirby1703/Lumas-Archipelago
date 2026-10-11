"""Capture the EggmanMedal native pickup before it removes its own actor.

Host arms an exact ORC-validated stage identity in an attributed Game Land playthrough.
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
    a.d(37, 1, 1, -0xa0)
    a.d(36, 0, 1, 16); a.emit(0x7C0802A6); a.d(36, 0, 1, 8)
    a.emit(0x7C000026); a.d(36, 0, 1, 12)
    registers = (3, 4, 5, 6, 7, 12)
    a.d(47, 3, 1, 20)
    a.emit(0x48000005); base = len(a.words)*4
    a.emit(0x7D8802A6); fix = len(a.words); a.d(14, 12, 12, 0)
    def equal(ra, rb):
        a.emit(0x7C000000 | ra << 16 | rb << 11); a.branch('end', 0x40820000)
    a.d(32, 6, 12, 0); a.d(11, 0, 6, 0); a.branch('end', 0x41820000)
    a.d(34, 6, 6, 0); a.d(32, 7, 12, 4); equal(6, 7)
    # Authenticate the currently picked actor, not a host-observed actor pointer.
    a.d(32, 5, 12, 8); a.d(11, 0, 5, 0); a.branch('end', 0x41820000)
    a.d(32, 6, 5, 0); a.d(15, 7, 0, 0x8076); a.d(14, 7, 7, -0x6bc8); equal(6, 7)
    a.d(32, 6, 5, 0x18); a.d(32, 7, 12, 20); equal(6, 7)
    a.d(32, 5, 5, 0x4c)
    for field, offset in ((0, 48), (4, 52)):
        a.d(32, 6, 5, field); a.d(32, 7, 12, offset); equal(6, 7)
    a.d(32, 6, 28, 0); a.d(15, 7, 0, 0x8078); a.d(14, 7, 7, -0x18ec); equal(6, 7)
    a.d(32, 6, 28, 0x34); a.d(32, 7, 12, 20); equal(6, 7)
    a.d(32, 5, 28, 0x64)
    a.d(32, 6, 5, 4); equal(6, 28)
    a.d(32, 4, 5, 8)
    a.d(32, 3, 5, 12)
    a.d(32, 6, 3, 0); a.d(15, 7, 0, 0x8077); a.d(14, 7, 7, 0x0fa0); equal(6, 7)
    a.d(32, 6, 3, 0x10); equal(6, 4)
    a.d(32, 6, 3, 0x1c); equal(6, 5)
    a.d(32, 6, 3, 0x14); a.d(32, 7, 12, 16); equal(6, 7)
    a.d(32, 6, 4, 0); a.emit(0x54C6033E)  # rlwinm r6,r6,0,12,31: native ORC ID
    a.d(32, 7, 12, 12); equal(6, 7)
    a.d(32, 5, 4, 0x18)
    # All 21 PAL Heart records have exactly one placement, instance zero.
    a.d(32, 6, 4, 0x1c); a.d(11, 0, 6, 1); a.branch('end', 0x40820000)
    for field, offset in ((0, 24), (4, 28), (8, 32)):
        a.d(32, 6, 5, field); a.d(32, 7, 12, offset); equal(6, 7)
    a.d(32, 6, 12, 40); a.d(32, 7, 12, 44)
    a.emit(0x7CC63B78); a.d(36, 6, 12, 40)
    a.label('end')
    a.d(46, 3, 1, 20)
    a.d(32, 0, 1, 12); a.emit(0x7C0FF120)
    a.d(32, 0, 1, 8); a.emit(0x7C0803A6)
    a.d(32, 0, 1, 16); a.d(14, 1, 1, 0xa0); a.emit(ORIGINAL)
    a.branch('return')
    offset = len(a.words)*4; a.words[fix] |= (offset-base)&0xffff
    for _ in range(14): a.emit(0)
    a.label('return')
    if len(a.words)%2 == 0: a.emit(0x60000000)
    a.emit(0)
    return a.finish(), offset


def installed_data(memory):
    words, offset = payload()
    try:
        result = inspect_c2(memory, HOOK, ORIGINAL, {'egg_medal': words}, ((offset, 56),), 'Eggman Heart')
    except MemoryUnavailable:
        from ..world_constants import load_data
        old = load_data('medal_hook_previous.json'); offset = old['offset']
        result = inspect_c2(memory, HOOK, ORIGINAL, {'previous':old['words']}, ((offset,44),), 'Eggman Heart')
    memory.medal_stage_capture = result.get('variant') == 'egg_medal'
    if not result['installed']: return None
    memory.medal_data_size = 56 if memory.medal_stage_capture else 44
    address = result['target'] + offset
    if not memory.medal_stage_capture:
        old = struct.unpack('>11I', memory.read_bytes(address,44))
        if (any(v and not valid_range(v,4) for v in (old[0],old[2],old[4],old[5],old[6]))
                or old[1] > 3 or old[7] >= 4096 or old[8] >= 1 << 21
                or old[8] and old[8] & (old[8]-1) or old[10] >= 1 << 21):
            raise MemoryUnavailable('unknown_revision: invalid legacy Eggman Heart data')
    values = struct.unpack('>14I', memory.read_bytes(address,56)) if memory.medal_stage_capture else (0,)*14
    if (any(v and not valid_range(v, 4) for v in (values[0], values[2], values[5]))
            or values[1] > 3 or values[4] != 0 or values[10] >= 1 << 21
            or values[11] >= 1 << 21 or values[11] and values[11] & (values[11]-1)):
        raise MemoryUnavailable('unknown_revision: invalid Eggman Heart stage capture data')
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
    selected = {name: code for name, code in slot['locations'].items() if name.endswith(' - Eggman Heart')}
    rows = [r for r in MEDALS if mask & (1 << r['index']) and r['location_name'] in selected
            and selected[r['location_name']] not in journal.data['pickup_checks']]
    if rows:
        journal.record_pickups([{'kind': 'egg_medal', 'mission': r['mission_id'],
                                'instance_key': f"{r['mission_id']}:{r['object_id']}:{r['instance_index']}",
                                'provenance': 'PAL_802F27C4_native_pickup', 'stage_epoch': snapshot.stage_epoch}
                               for r in rows], {}, {selected[r['location_name']] for r in rows})
        import logging
        logging.getLogger('Client').info('Pickup detected: Eggman Hearts %s; Location queued: %s',
            [r['location_name'] for r in rows], [selected[r['location_name']] for r in rows])


def configure(memory, snapshot, journal):
    address = installed_data(memory)
    if address is None:
        return {'available': False, 'reason': 'Eggman Heart hook not installed: check enabled code and Gecko RAM-table capacity; use the current compact export'}
    if not memory.medal_stage_capture:
        return {'available':False,'armed':False,'reason':'Update Gecko codes for stage-level Heart capture'}
    chain = memory.resolve_flags_ptr()
    stage = next(iter(snapshot.evidence.get('native_data', {}).get('stage_objects', [])), {})
    from ..medals import MEDALS
    row = next((r for r in MEDALS if r['mission_id'] == stage.get('mission', snapshot.actual_mission)), None)
    context = stage.get('stage', 0) if snapshot.scene == 'gameplay' else 0
    if not context: row = None
    manager = memory.read_ptr_checked(context+0x18, 0x20) if row else 0
    position = struct.unpack('>3I', struct.pack('>3f', *row['position'])) if row else (0,0,0)
    mission = struct.unpack('>2I', row['mission_id'].encode().ljust(8,b'\0')) if row else (0,0)
    values = (chain[1], chain[2], context if row else 0, row['object_id'] if row else 0,
              row['instance_index'] if row else 0, manager, *position, identity_tag(journal.identity),
              memory.read_u32(address+40), 1 << row['index'] if row else 0, *mission)
    old = struct.unpack('>14I', memory.read_bytes(address, 56))
    if old == values: return {'pickup_recorded':bool(row and row['code'] in journal.data['pickup_checks']), 'acknowledged':bool(row and row['code'] in journal.data.get('acknowledged_locations',())), 'available': True, 'armed': bool(row), 'strategy':'stage_identity', 'mission':stage.get('mission'), 'expected_location':row['location_name'] if row else None, 'actor_found':bool(stage.get('medals')), 'pickup_latch':memory.read_u32(address+40), 'reason':None if row else 'No attributed Game Land stage identity'}
    # Actor zero disables capture during a multiword context change.
    if old[2]: memory.write_u32(address+8, 0, expected=old[2], operation='egg_medal_controls')
    if old[9] != values[9]:
        before = memory.read_u32(address+40)
        if before: memory.write_u32(address+40, 0, expected=before, operation='egg_medal_controls')
    for i, value in enumerate(values):
        if i in (2, 10): continue
        before = memory.read_u32(address+i*4)
        if before != value: memory.write_u32(address+i*4, value, expected=before, operation='egg_medal_controls')
    if values[2]: memory.write_u32(address+8, values[2], expected=0, operation='egg_medal_controls')
    return {'pickup_recorded':bool(row and row['code'] in journal.data['pickup_checks']), 'acknowledged':bool(row and row['code'] in journal.data.get('acknowledged_locations',())), 'available': True, 'armed': bool(row), 'strategy':'stage_identity', 'mission':stage.get('mission'), 'expected_location':row['location_name'] if row else None, 'actor_found':bool(stage.get('medals')), 'pickup_latch':memory.read_u32(address+40), 'reason':None if row else 'No attributed Game Land stage identity'}


def gecko_lines():
    words, _ = payload()
    return (['$AP PAL Eggman Heart pickup capture', '20000000 534E4350', '28000004 00003850',
             '28000006 00000000', f'20{HOOK-0x80000000:06X} {ORIGINAL:08X}',
             f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}']
            + [f'{words[i]:08X} {words[i+1]:08X}' for i in range(0, len(words), 2)]
            + ['E0000000 80008000'])
