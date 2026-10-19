"""PAL native speed selection/simulation and ordinary White Boost query gates.

Only Gecko installs executable code. Seed ownership is checked against the
selected native profile inside each thunk, independently of host polling.
No native calls or CTR changes; LR, CR and scratch GPRs are preserved.
The ordinary-use hook replaces only the displaced instruction's f1 output.
"""
from .gecko import cached_payload
import struct
from .capsule_refresh import PPC, valid_native_control_index
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


@cached_payload
def payload(kind, compact=True, temporary=True, drain=True, lean=True, register_abi=True, pic_base=True, volatile_return=True, caller_lr_dead=True):
    if not compact: temporary = False
    a = PPC(); hook, original = HOOKS[kind]
    short = compact and lean and register_abi and pic_base
    # Only volatile CR0 is changed. Boost-use/speed-UI overwrite it before
    # branching; the query/get/set hooks finish their native functions, whose
    # PPC call ABI does not preserve CR0. CR2..4 remain untouched.
    dead_lr=short and caller_lr_dead and kind in ('boost_use','boost_query')
    preserve_cr = not (short and (kind in ('boost_use','speed_ui') or volatile_return and kind in ('boost_query','boost_add','speed_get','speed_set')))
    output = 3 if kind in ('boost', 'speed_get') else 0 if kind == 'speed_ui' else None
    frame = 0xa0 if compact else 0x40
    saved = (3, 4, 6, 7, 12)
    a.d(37, 1, 1, -frame)
    if compact:
        a.d(47, 0, 1, 16)
        if register_abi:
            if not dead_lr:a.emit(0x7FE802A6)  # saved r31 holds LR across inline, call-free gate
            if preserve_cr:a.emit(0x7F800026)  # saved r28 holds CR; restored by lmw
        else:
            a.emit(0x7C0802A6); a.d(36, 0, 1, 144)
            a.emit(0x7C000026); a.d(36, 0, 1, 148)
    else:
        a.d(36, 0, 1, 16); a.emit(0x7C0802A6); a.d(36, 0, 1, 8)
        a.emit(0x7C000026); a.d(36, 0, 1, 12)
        for r in saved: a.d(36, r, 1, 20 + saved.index(r)*4)
    # Share the displaced load/store across both ownership branches. Keep
    # older exact layouts available to the verifier during client updates.
    if lean and compact and kind == 'speed_get': a.emit(original)
    a.emit(0x48000005); base = len(a.words)*4
    a.emit(0x7D8802A6); fix = len(a.words)
    if not short:a.d(14, 12, 12, 0)
    if lean and compact and kind == 'speed_ui': a.d(32, 0, 1, 16)
    a.d(32, 6, 12, 0); a.d(11, 0, 6, 0); a.branch('vanilla', 0x41820000)
    a.d(34, 6, 6, 0); a.d(32, 7, 12, 4)
    a.emit(0x7C063800); a.branch('vanilla', 0x40820000)  # cmpw r6,r7
    if kind in ('boost', 'boost_use', 'boost_query', 'boost_add'):
        if kind == 'boost':
            # Index zero is a coloured transformation, not White Boost.
            # Keep this compatibility hook inert; never deny native Drill.
            a.branch('vanilla')
        elif kind == 'boost_use':
            # 800CD720 keeps the wrapper argument in r30. The original
            # 80033A44 resolves wrapper+28 -> player+8C -> provider;
            # 800381E0 reads provider+24 for Super's separate Boost mode.
            a.d(32, 6, 30, 0x28); a.d(32, 6, 6, 0x8c); a.d(32, 6, 6, 0x24)
            a.d(11, 0, 6, 1); a.branch('vanilla', 0x41820000)
        a.d(32, 7, 12, 12); a.emit(0x7C033800); a.branch('vanilla', 0x40820000)
        a.d(32, 7, 12, 16); a.d(11, 0, 7, 0 if kind == 'boost_add' and temporary else 1); a.branch('vanilla', 0x41820000 if kind == 'boost_add' and temporary else 0x40820000)
        if kind == 'boost': a.d(14, 3, 0, 0)  # unreachable compatibility body
        elif kind == 'boost_add':
            if temporary and drain:
                # The original 801014F0 routine also handles negative Boost
                # consumption. f1 is its delta; f2 is its native zero lower
                # clamp bound (loaded at 801014F8). Deny positive grants only.
                # Preserve f0/f2/f3 and restore the caller's saved CR below.
                a.emit(0xFC011040)  # fcmpu cr0,f1,f2
                a.branch('vanilla', 0x41800000)  # negative delta consumes gauge
            # Preserve the pre-existing gauge; deny only the new pickup/script
            # amount. Super's separate provider bypasses this native routine.
            a.d(48, 1, 3, 8)
        else:
            # PAL r2=808FC5C0; original lower-clamp float at 808F6040
            # is zero. Reuse it instead of allocating another data word.
            a.d(48, 1, 2 if lean and compact else 12, -0x6580 if lean and compact else 20)
        a.branch('restore')
    else:
        if kind == 'speed_ui':
            a.d(32, 6, 29, 0x114); a.d(11, 0, 6, 0); a.branch('vanilla', 0x40820000)
            if not (lean and compact): a.d(32, 0, 1, 16)
        if kind == 'speed_get' and not (lean and compact): a.emit(original)
        a.d(32, 7, 12, 8)
        target = 3 if kind == 'speed_get' else 4 if kind == 'speed_set' else 0
        a.emit(0x7C003800 | target << 16)  # cmpw target,r7
        a.branch('selected', 0x40810000)
        a.mr(target, 7)
        a.label('selected')
        if not (lean and compact):
            if kind != 'speed_get': a.emit(original)
            a.branch('restore')
    a.label('vanilla')
    if kind == 'speed_ui' and not (lean and compact): a.d(32, 0, 1, 16)
    if not (lean and compact and kind == 'speed_get'): a.emit(original)
    a.label('restore')
    if compact:
        if output is not None: a.d(36, output, 1, 16+output*4)
        if register_abi:
            if preserve_cr:a.emit(0x7F8FF120)
            if not dead_lr:a.emit(0x7FE803A6)
        else:
            a.d(32, 0, 1, 148); a.emit(0x7C0FF120)
            a.d(32, 0, 1, 144); a.emit(0x7C0803A6)
        # lmw r0,16(r1) is an invalid PowerPC form: its base is in the
        # destination range. Never reload the stack base during a restore.
        a.d(46, 2, 1, 24)
        a.d(32, 0, 1, 16)
    else:
        for r in saved:
            if r != output: a.d(32, r, 1, 20 + saved.index(r)*4)
    # Keep the UI's displaced r0 output while restoring CR/LR with r6.
    if not compact:
        a.d(32, 6, 1, 12); a.emit(0x7CCFF120)
        a.d(32, 6, 1, 8); a.emit(0x7CC803A6)
        a.d(32, 6, 1, 28)
        if output != 0: a.d(32, 0, 1, 16)
    a.d(14, 1, 1, frame); a.branch('return')
    data = len(a.words)*4
    if short:
        for i,w in enumerate(a.words):
            if w>>26 in (32,48) and (w>>16)&31==12:
                a.words[i]=(w&0xffff0000)|(((w&0xffff)+data-base)&0xffff)
    else:a.words[fix] |= (data-base)&0xffff
    for _ in range(3 if compact and temporary and kind.startswith('speed') else 6 if not compact or kind in ('boost_use','boost_query') and not lean else 5): a.emit(0)
    a.label('return')
    if len(a.words)%2 == 0: a.emit(0x60000000)
    a.emit(0)
    return a.finish(), data


def installed(memory, kind):
    hook, original = HOOKS[kind]; words, offset = payload(kind)
    from ..world_constants import load_data
    previous_words, previous_offset = payload(kind, compact=False, temporary=False, lean=False,register_abi=False)
    legacy = load_data('gameplay_hook_legacy.json').get(kind)
    old_compact, old_offset = payload(kind, temporary=False, lean=False,register_abi=False)
    no_drain, no_drain_offset = payload(kind, drain=False, lean=False,register_abi=False)
    before_lean, before_lean_offset = payload(kind, lean=False,register_abi=False)
    stack_lr,stack_lr_offset=payload(kind,register_abi=False)
    layouts = [(kind, words, offset), ('stack_lr',stack_lr,stack_lr_offset), ('before_lean', before_lean, before_lean_offset), ('before_drain', no_drain, no_drain_offset), ('before_temporary', old_compact, old_offset), ('previous', previous_words, previous_offset)]
    old_lr,old_lr_offset=payload(kind,caller_lr_dead=False)
    layouts.append(('before_dead_lr',old_lr,old_lr_offset))
    before_hover, before_hover_offset=payload(kind,volatile_return=False,caller_lr_dead=False)
    layouts.append(('before_hover',before_hover,before_hover_offset))
    before_drill=load_data('gameplay_before_drill.json').get(kind)
    if before_drill:layouts.append(('before_drill',before_drill['words'],before_drill['offset']))
    before_stack=load_data('gameplay_before_stack_restore.json').get(kind)
    if before_stack:layouts.append(('before_stack',before_stack['words'],before_stack['offset']))
    if legacy: layouts.append(('legacy', legacy['words'], legacy['offset']))
    for name, candidate, candidate_offset in layouts:
        try:
            size = 12 if name in (kind, 'before_stack', 'before_dead_lr', 'before_hover', 'before_drill', 'stack_lr', 'before_lean') and kind.startswith('speed') else 20
            result = inspect_c2(memory, hook, original, {name:candidate}, ((candidate_offset,size),), label=kind)
            offset = candidate_offset
            break
        except MemoryUnavailable as error:
            failure = error
    else: raise failure
    if not result['installed']: return None
    if kind == 'boost_add': memory.boost_consumption_safe = name in (kind, 'before_stack', 'before_dead_lr', 'before_hover', 'before_drill', 'stack_lr', 'before_lean')
    address = result['target'] + offset
    values = struct.unpack('>'+'I'*(size//4), memory.read_bytes(address,size))
    owner, index, maximum, model, locked = (*values, 0, 0) if size == 12 else values
    if not hasattr(memory, 'gameplay_data_sizes'): memory.gameplay_data_sizes = {}
    memory.gameplay_data_sizes[address] = size
    if (owner and not valid_range(owner, 1) or not valid_native_control_index(memory, owner, index) or maximum > 4
            or model and not valid_range(model, 0x30) or locked > 2):
        raise MemoryUnavailable('unknown_revision: invalid native gameplay control data')
    return address


def configure(memory, snapshot, owned, slot, temporary_boost=False, kinds=None):
    from ..Items import GAME_LAND_SPEED
    from .state import live_control_profile
    chain = live_control_profile(memory, snapshot, getattr(getattr(memory, 'write_guard', None), 'guard', None))
    speed_locked = (slot.get('game_land_speed_items') and slot['options'].get('game_land_checks')
                    and slot['options'].get('movement_unlocks'))
    maximum = min(4, owned['counts'][GAME_LAND_SPEED]) if speed_locked else 4
    model = snapshot.boost_address - 8 if snapshot.boost_address is not None else 0
    locked = int(bool(slot['options'].get('boost_lock') and not owned['counts']['White Boost Wisp']))
    values = (chain[1], chain[2], maximum, model, 2 if locked and temporary_boost else locked)
    status = {}
    for kind in (HOOKS if kinds is None else kinds):
        # Neutralize the previously installed erroneous coloured-Wisp gate too.
        desired = (*values[:4], 0) if kind == 'boost' else values
        address = installed(memory, kind)
        status[kind] = bool(address)
        if address is None: continue
        size = memory.gameplay_data_sizes[address]
        desired = desired[:size//4]
        if tuple(struct.unpack('>'+'I'*(size//4), memory.read_bytes(address, size))) == desired:
            continue
        if memory.read_u32(address):
            memory.write_u32(address, 0, expected=memory.read_u32(address), operation='gameplay_controls')
        for i, value in enumerate(desired[1:], 1):
            current = memory.read_u32(address+i*4)
            if current != value:
                memory.write_u32(address+i*4, value, expected=current, operation='gameplay_controls')
        memory.write_u32(address, values[0], expected=0, operation='gameplay_controls')
    return {'installed': status, 'maximum_speed': maximum+1, 'boost_locked': bool(locked and not temporary_boost), 'temporary_boost':bool(locked and temporary_boost),
            'boost_consumption_safe':getattr(memory, 'boost_consumption_safe', False),
            'boost_lock_active': bool(locked and model and all(status.get(k,False) for k in ('boost_use', 'boost_query', 'boost_add'))),
            'speed_controls_active': all(status.get(k,False) for k in ('speed_get', 'speed_set', 'speed_ui'))}


def gecko_lines(close_scope=True):
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
    from .map_refresh import HOOK, ORIGINAL, payload as map_payload
    words, _ = map_payload()
    lines += [f'20{HOOK-0x80000000:06X} {ORIGINAL:08X}', f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}']
    lines += [f'{words[i]:08X} {words[i+1]:08X}' for i in range(0,len(words),2)]
    # The combined four-group export closes this scope in its Medal group;
    # a standalone export remains independently terminated.
    if close_scope: lines += ['E0000000 80008000']
    return lines
