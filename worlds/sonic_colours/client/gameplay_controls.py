"""PAL native speed selection/simulation and ordinary White Boost query gates.

Only Gecko installs executable code. Seed ownership is checked against the
selected native profile inside each thunk, independently of host polling.
No native calls or CTR changes; LR, CR and scratch GPRs are preserved.
The ordinary-use hook replaces only the displaced instruction's f1 output.
"""
import struct
from .capsule_refresh import PPC
from .gecko import inspect_c2
from .memory import MemoryUnavailable, valid_range

HOOKS = {
    'boost': (0x801014E0, 0x8863002C),
    'boost_use': (0x800CD730, 0xC0230008),
    'boost_query': (0x8020E208, 0xC0230008),
    'boost_add': (0x80101510, 0xEC20082A),
    'speed_get': (0x8026FF40, 0x80630004),
    'speed_set': (0x8026FF68, 0x90830004),
    'speed_ui': (0x802EEB10, 0x901B0118),
}


def payload(kind):
    a = PPC(); hook, original = HOOKS[kind]
    output = 3 if kind in ('boost', 'speed_get') else 0 if kind == 'speed_ui' else None
    a.d(37, 1, 1, -0x40)
    a.d(36, 0, 1, 16); a.emit(0x7C0802A6); a.d(36, 0, 1, 8)
    a.emit(0x7C000026); a.d(36, 0, 1, 12)
    for r in (3, 4, 6, 7, 12): a.d(36, r, 1, 20 + (3, 4, 6, 7, 12).index(r)*4)
    a.emit(0x48000005); base = len(a.words)*4
    a.emit(0x7D8802A6); fix = len(a.words); a.d(14, 12, 12, 0)
    a.d(32, 6, 12, 0); a.d(11, 0, 6, 0); a.branch('vanilla', 0x41820000)
    a.d(34, 6, 6, 0); a.d(32, 7, 12, 4)
    a.emit(0x7C063800); a.branch('vanilla', 0x40820000)  # cmpw r6,r7
    if kind in ('boost', 'boost_use', 'boost_query', 'boost_add'):
        if kind == 'boost':
            # Index zero is a coloured transformation, not White Boost.
            # Keep this compatibility hook inert; never deny native Drill.
            a.branch('vanilla')
        elif kind == 'boost_use':
            # 800CD708's receiver r30 is the native player; mode 1 uses
            # the separate native Boost provider (800381E0/8020E1CC).
            a.d(32, 6, 30, 0x8c); a.d(32, 6, 6, 0x24)
            a.d(11, 0, 6, 1); a.branch('vanilla', 0x41820000)
        a.d(32, 7, 12, 12); a.emit(0x7C033800); a.branch('vanilla', 0x40820000)
        a.d(32, 7, 12, 16); a.d(11, 0, 7, 1); a.branch('vanilla', 0x40820000)
        if kind == 'boost': a.d(14, 3, 0, 0)  # unreachable compatibility body
        elif kind == 'boost_add':
            # Preserve the pre-existing gauge; deny only the new pickup/script
            # amount. Super's separate provider bypasses this native routine.
            a.d(48, 1, 3, 8)
        else: a.d(48, 1, 12, 20)  # query returns zero, gauge is untouched
        a.branch('restore')
    else:
        if kind == 'speed_ui':
            a.d(32, 6, 29, 0x114); a.d(11, 0, 6, 0); a.branch('vanilla', 0x40820000)
            a.d(32, 0, 1, 16)
        if kind == 'speed_get': a.emit(original)
        a.d(32, 7, 12, 8)
        target = 3 if kind == 'speed_get' else 4 if kind == 'speed_set' else 0
        a.emit(0x7C003800 | target << 16)  # cmpw target,r7
        a.branch('selected', 0x40810000)
        a.mr(target, 7)
        a.label('selected')
        if kind != 'speed_get': a.emit(original)
        a.branch('restore')
    a.label('vanilla')
    if kind == 'speed_ui': a.d(32, 0, 1, 16)
    a.emit(original)
    a.label('restore')
    for r in (3, 4, 6, 7, 12):
        if r != output: a.d(32, r, 1, 20 + (3, 4, 6, 7, 12).index(r)*4)
    # Keep the UI's displaced r0 output while restoring CR/LR with r6.
    a.d(32, 6, 1, 12); a.emit(0x7CCFF120)  # mtcrf 255,r6
    a.d(32, 6, 1, 8); a.emit(0x7CC803A6)  # mtlr r6
    a.d(32, 6, 1, 28)
    if output != 0: a.d(32, 0, 1, 16)
    a.d(14, 1, 1, 0x40); a.branch('return')
    data = len(a.words)*4; a.words[fix] |= (data-base)&0xffff
    for _ in range(6): a.emit(0)  # five mutable words and immutable float zero
    a.label('return')
    if len(a.words)%2 == 0: a.emit(0x60000000)
    a.emit(0)
    return a.finish(), data


def installed(memory, kind):
    hook, original = HOOKS[kind]; words, offset = payload(kind)
    from ..world_constants import load_data
    legacy = load_data('gameplay_hook_legacy.json').get(kind)
    variants = {kind: words}
    if legacy and legacy['offset'] == offset:
        variants['legacy'] = legacy['words']
    if legacy and legacy['offset'] != offset:
        # Exact historical layout has a different embedded-data offset.
        try:
            result = inspect_c2(memory, hook, original, variants, ((offset, 20),), label=kind)
        except MemoryUnavailable:
            result = inspect_c2(memory, hook, original, {'legacy':legacy['words']},
                                ((legacy['offset'],20),), label=kind)
            offset = legacy['offset']
    else:
        result = inspect_c2(memory, hook, original, variants, ((offset, 20),), label=kind)
    if not result['installed']: return None
    address = result['target'] + offset
    owner, index, maximum, model, locked = struct.unpack('>5I', memory.read_bytes(address, 20))
    if (owner and not valid_range(owner, 1) or index > 3 or maximum > 4
            or model and not valid_range(model, 0x30) or locked > 1):
        raise MemoryUnavailable('unknown_revision: invalid native gameplay control data')
    return address


def configure(memory, snapshot, owned, slot):
    from ..Items import GAME_LAND_SPEED
    chain = memory.resolve_flags_ptr(allow_working=True)
    maximum = min(4, owned['counts'][GAME_LAND_SPEED]) if slot.get('game_land_speed_items') else 4
    model = snapshot.boost_address - 8 if snapshot.boost_address is not None else 0
    locked = int(bool(slot['options'].get('boost_lock') and not owned['counts']['White Boost Wisp']))
    values = (chain[1], chain[2], maximum, model, locked)
    status = {}
    for kind in HOOKS:
        # Neutralize the previously installed erroneous coloured-Wisp gate too.
        desired = (*values[:4], 0) if kind == 'boost' else values
        address = installed(memory, kind)
        status[kind] = bool(address)
        if address is None: continue
        if tuple(struct.unpack('>5I', memory.read_bytes(address, 20))) == desired:
            continue
        if memory.read_u32(address):
            memory.write_u32(address, 0, expected=memory.read_u32(address), operation='gameplay_controls')
        for i, value in enumerate(desired[1:], 1):
            current = memory.read_u32(address+i*4)
            if current != value:
                memory.write_u32(address+i*4, value, expected=current, operation='gameplay_controls')
        memory.write_u32(address, values[0], expected=0, operation='gameplay_controls')
    return {'installed': status, 'maximum_speed': maximum+1, 'boost_locked': bool(locked),
            'boost_lock_active': bool(locked and model and all(status[k] for k in ('boost_use', 'boost_query', 'boost_add'))),
            'speed_controls_active': all(status[k] for k in ('speed_get', 'speed_set', 'speed_ui'))}


def gecko_lines():
    lines = ['$AP PAL speed and White Boost gates', '20000000 534E4350', '28000004 00003850', '28000006 00000000']
    # Dolphin skips an entire group if it exceeds the remaining low-MEM1
    # codelist budget. Do not export the inert historical coloured-Wisp query.
    # Keep recognizing/neutralizing it above for previously installed builds.
    # One shared conditional scope installs all real controls on the first
    # handler pass; each original instruction must match. Once installed, the
    # first displaced instruction fails its condition on subsequent passes.
    for kind, (hook, original) in HOOKS.items():
        if kind == 'boost': continue
        words, _ = payload(kind)
        lines += [f'20{hook-0x80000000:06X} {original:08X}', f'C2{hook-0x80000000:06X} {len(words)//2:08X}']
        lines += [f'{words[i]:08X} {words[i+1]:08X}' for i in range(0,len(words),2)]
    lines += ['E0000000 80008000']
    return lines
