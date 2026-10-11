"""EXPERIMENTAL DME-only PPC injector. EXPECT CRASHES / JIT CACHE FAILURES.

No Gecko cheat codes or external files. This injector is deliberately not used
without the explicit CLI opt-in; the guest scratch space is a candidate seen
zero in PAL captures, *not* a proved permanent allocation. Writing guest code
via DME does not guarantee Dolphin JIT cache invalidation. An installed branch
is not evidence the newly written code was executed.

Intended for controlled PAL SNCP8P revision-0 testing on a disposable save,
with all Gecko codes DISABLED and exactly one Dolphin process. Always stop the
emulator after testing; this code is not safely unpatchable mid-flight.
"""
import struct
from .memory import MemoryUnavailable

# Original PAL dumps with Gecko DISABLED show this code-handler scratch region
# completely zero, while 0x80003000 onward is demonstrably occupied by Wii
# runtime data. Never extend the guest arena above 0x80003000.
ARENA_START = 0x80001800
ARENA_END = 0x80003000


def _branch(from_address, to_address):
    delta = to_address - from_address
    if delta % 4 or not -(1 << 25) <= delta < (1 << 25):
        raise MemoryUnavailable('experimental branch out of PowerPC range')
    return 0x48000000 | (delta & 0x03FFFFFC)


def planned_hooks(include_movement=False):
    from . import capsule_refresh, progression_hook, gameplay_controls, medal_hook, map_refresh
    entries = [(capsule_refresh.HOOK, capsule_refresh.ORIGINAL, capsule_refresh.payload_words(), 'capsule'),
               (progression_hook.HOOK, progression_hook.ORIGINAL, progression_hook.payload()[0], 'progression')]
    for kind, (address, original) in gameplay_controls.HOOKS.items():
        if kind != 'boost':  # intentionally inert historical compatibility hook
            entries.append((address, original, gameplay_controls.payload(kind)[0], kind))
    entries.extend([(medal_hook.HOOK, medal_hook.ORIGINAL, medal_hook.payload()[0], 'eggman_heart'),
                    (map_refresh.HOOK, map_refresh.ORIGINAL, map_refresh.payload()[0], 'grand_map')])
    if include_movement:
        from . import movement_gate
        entries.append((movement_gate.HOOK, movement_gate.ORIGINAL,
                        movement_gate.payload()[0], 'movement'))
    entries.sort(key=lambda row: row[0])
    return entries


def plan(include_movement=False):
    patches = []
    cursor = ARENA_START
    for address, original, raw_words, label in planned_hooks(include_movement):
        words = list(raw_words)
        size = len(words)*4
        if cursor + size > ARENA_END:
            raise MemoryUnavailable('experimental code arena too small')
        if words[-1] != 0:
            raise MemoryUnavailable('unexpected C2 return placeholder')
        if label == 'movement':
            from .movement_gate import payload, DENIED_CONTINUATION
            _, deny_index, _ = payload()
            words[deny_index] = _branch(cursor + deny_index*4, DENIED_CONTINUATION)
        words[-1] = _branch(cursor + size - 4, address + 4)
        code = struct.pack('>'+'I'*len(words),*words)
        patches.append((address, original, cursor, code, label))
        cursor += size
    return patches


def install(memory, enable_movement=False):
    """Opt-in experimental code write; NO guarantee of Dolphin JIT execution.

    Stages the complete payloads before installing the individual hook branches.
    A failed/partial install is NOT repaired or rolled back while the game runs.
    Restart emulation after errors. There is no claim of cache coherency.
    """
    memory.verify_revision()
    patches = plan(include_movement=enable_movement)
    payload_bytes = b''.join(row[3] for row in patches)
    if any(memory.read_u32(site) != original for site, original, *_ in patches):
        # We must never mix an active Gecko handler and this injector, or patch
        # over an unrecognized executable revision, even in this test mode.
        raise MemoryUnavailable('EXPERIMENT BLOCKED: restore original game instructions; disable all Gecko codes and restart Dolphin')
    before = memory.read_bytes(ARENA_START, len(payload_bytes))
    if before != bytes(len(payload_bytes)):
        raise MemoryUnavailable('EXPERIMENT BLOCKED: candidate guest scratch region is not entirely zero; disable Gecko and restart')
    # Explicit exact write allowlist. The guard refuses all other executable
    # writes, and the ordinary readback confirms only guest RAM bytes.
    entries = {arena: (bytes(len(code)), code) for _,_,arena,code,_ in patches}
    entries.update({hook: (original.to_bytes(4,'big'), _branch(hook, arena).to_bytes(4,'big'))
                    for hook,original,arena,code,label in patches})
    memory._direct_hook_transaction = entries
    written = []
    try:
        for hook, original, arena, code, label in patches:
            memory.write_bytes_verified(arena, code, expected=bytes(len(code)), operation='experimental_code')
            written.append('payload:'+label)
        for hook, original, arena, code, label in patches:
            memory.write_u32(hook, _branch(hook,arena), expected=original, operation='experimental_code')
            written.append('branch:'+label)
    finally:
        memory._direct_hook_transaction = None
    memory.verify_revision()
    return {'installed_in_guest_ram': True, 'movement_hook_included': bool(enable_movement), 'guest_arena':f'0x{ARENA_START:08X}',
            'payload_bytes':len(payload_bytes), 'hook_count':len(patches),
            'jit_execution_verified':False, 'status':'EXPERIMENTAL: guest code written; JIT cache coherence unknown',
            'instructions':'Disable Gecko, restart Dolphin, observe gameplay and status; after testing restart Dolphin again'}


def inspect(memory, enable_movement=False):
    """Read-only signature check on an existing direct installation."""
    patches=plan(include_movement=enable_movement)
    for hook, original, arena, code, label in patches:
        if not recognize_branch(memory, hook, original, (hook, original, arena, code, label)):
            return False
    return True


def _mutable_span(label):
    """Exact data-word spans owned by existing guarded PPC thunks."""
    if label == 'movement':
        from .movement_gate import payload
        return payload()[2], 8
    if label == 'capsule':
        from .capsule_refresh import payload_words, data_offset
        return data_offset(payload_words()), 12
    if label == 'progression':
        from .progression_hook import payload
        return payload()[1], 32
    if label in ('boost_use', 'boost_query', 'boost_add', 'speed_get', 'speed_set', 'speed_ui'):
        from .gameplay_controls import payload
        return payload(label)[1], (12 if label.startswith('speed') else 20)
    if label == 'eggman_heart':
        from .medal_hook import payload
        return payload()[1], 56
    if label == 'grand_map':
        from .map_refresh import payload
        return payload()[1], 16
    raise MemoryUnavailable('unrecognized experimental direct payload')


def recognize_branch(memory, hook, original, candidate):
    """Return true only if a direct payload (excluding guarded data) matches.

    This allows verify_revision to authenticate the original PAL DOL during a
    PARTIALLY installed experiment without blessing arbitrary guest code.
    """
    address, _original, arena, code, label = candidate
    if hook != address or original != _original or memory.read_u32(hook) != _branch(hook, arena):
        return False
    size = len(code)
    actual = bytearray(memory.read_bytes(arena, size))
    expected = bytearray(code)
    offset, mutable_size = _mutable_span(label)
    if offset + mutable_size > size - 4: return False
    actual[offset:offset+mutable_size] = bytes(mutable_size)
    expected[offset:offset+mutable_size] = bytes(mutable_size)
    return actual == expected
