"""Opt-in PAL native movement transition experiment.

The read-only evidence ties player+0x90 -> controller (vtable 8075FA3C),
controller+0x40 -> nested state machine, and its requested ID at +0x60.
The original 80033188 instruction copies this request into the active state.
An explicit player/controller/owner match is required before a deny branch
skips the transition at 800331EC. No post-entry state is overwritten.

This is NOT a live-verified movement lock. It is emitted only into the
Gecko-DISABLED experimental direct hook arena, whose JIT coherency remains
unverified. The normal Gecko installation NEVER enables these restrictions.
Underwater jumps and oxygen are NOT wired: no true native oxygen clock or
underwater jump entry gate has been proved. These require further capture.
"""
from .capsule_refresh import PPC
from .memory import MemoryUnavailable, valid_range

HOOK = 0x80033188
ORIGINAL = 0x801F0020                 # lwz r0,0x20(r31)
DENIED_CONTINUATION = 0x800331EC    # post-transition state update in the original DOL
CONTROLLER_VTABLE = 0x8075FA3C
PLAYER_VTABLE = 0x8075AEF8
# Permission bit 1 = owned/unlocked. State 43 is crouch (first copy),
# state 41 is Slide (second copy). 9 = Jump Dash (user's Mid-Air Boost).
STATE_PERMISSION = {8: 0, 9: 1, 13: 2, 39: 3, 40: 3, 41: 4, 43: 5, 44: 6}
CAPABILITY_NAMES = ('Double Jump', 'Mid-Air Boost', 'Homing Attack',
                    'Wall Jump', 'Slide', 'Crouch', 'Ground Pound')
DATA_WORDS = 2                 # controlled controller pointer + ability mask
DENY_PLACEHOLDER = 0xDEAD331E


def permissions(counts):
    """Return native feature mask, NEVER derived from Wisp/normal Boost."""
    return sum(1 << bit for bit, present in enumerate((
        counts['Double Jump'] > 0,
        counts['Mid-Air Boost'] > 0,
        counts['Homing Attack'] > 0,
        counts['Wall Jump'] > 0,
        counts['Progressive Crouch'] >= 2,
        counts['Progressive Crouch'] >= 1,
        counts['Ground Pound'] > 0,
    )) if present)


def payload():
    """Return PPC words, index of denied jump and authenticated data offset.

    Control data lives in the same direct-hook allocation. The host writes
    only this exact two-word range with compare/readback validation. The hook
    is inert until the host supplies a verified living player's controller.
    """
    a = PPC()
    a.d(37, 1, 1, -0x40)       # stwu r1,-64(r1)
    for reg, off in ((9, 8), (10, 12), (11, 16), (12, 20)):
        a.d(36, reg, 1, off)
    a.emit(0x7D600026)        # mfcr r11
    a.d(36, 11, 1, 24)
    a.emit(0x7D6802A6)        # mflr r11
    a.d(36, 11, 1, 28)
    a.emit(0x48000005)        # bl +4 for PC-relative data, LR restored on exit
    pic_base = len(a.words)*4
    a.emit(0x7D8802A6)        # mflr r12
    fix_index = len(a.words)
    a.d(14, 12, 12, 0)         # addi r12,r12, data-pc
    a.d(32, 9, 12, 0)          # lwz r9, controller
    a.d(11, 0, 9, 0); a.branch('allow', 0x41820000)
    a.d(14, 10, 31, -0x40)   # actual state-machine = controller+0x40
    a.emit(0x7C0A4800)       # cmpw r10,r9
    a.branch('allow', 0x40820000)
    a.d(32, 10, 9, 0); a.d(15, 11, 0, CONTROLLER_VTABLE >> 16)
    a.d(24, 11, 11, CONTROLLER_VTABLE & 0xffff)
    a.emit(0x7C0A5800); a.branch('allow', 0x40820000)
    a.d(32, 10, 9, 4)        # controller+4 -> Sonic actor
    a.d(11, 0, 10, 0); a.branch('allow', 0x41820000)
    a.d(32, 11, 10, 0)
    a.d(15, 9, 0, PLAYER_VTABLE >> 16); a.d(24, 9, 9, PLAYER_VTABLE & 0xffff)
    a.emit(0x7C0B4800); a.branch('allow', 0x40820000)
    a.d(32, 9, 10, 0x90)      # player's native controller must refer back
    a.d(14, 10, 31, -0x40)
    a.emit(0x7C095000); a.branch('allow', 0x40820000)
    a.d(32, 10, 12, 4)       # signed permission bitmask
    a.d(32, 0, 31, 0x20)    # native requested state, BEFORE overwriting current
    for state, bit in STATE_PERMISSION.items():
        a.d(11, 0, 0, state); a.branch(f'next_{state}', 0x40820000)
        a.d(28, 9, 10, 1 << bit)    # andi. r9,r10,permission-bit
        a.branch('deny', 0x41820000)
        a.branch('allow')
        a.label(f'next_{state}')
    a.branch('allow')
    def restore():
        a.d(32, 11, 1, 24); a.emit(0x7D6FF120) # mtcrf 0xff,r11
        a.d(32, 11, 1, 28); a.emit(0x7D6803A6) # mtlr r11
        for reg, off in ((12,20),(11,16),(10,12),(9,8)):
            a.d(32, reg, 1, off)
        a.d(14, 1, 1, 0x40)
    a.label('deny')
    restore()
    deny_index = len(a.words)
    a.emit(DENY_PLACEHOLDER)  # filled by direct_hooks.plan with relative branch
    a.label('allow')
    restore()
    a.emit(ORIGINAL)          # preserve overwritten lwz r0,0x20(r31)
    a.branch('return')        # over data cells
    data_offset = len(a.words)*4
    a.emit(0)                 # controller address, armed LAST
    a.emit(0)                 # independent movement permission mask
    a.label('return')
    a.emit(0)                 # filled by direct_hooks.plan (HOOK + 4)
    words = a.finish()
    words[fix_index] |= (data_offset - pic_base) & 0xffff
    return words, deny_index, data_offset


def observed(memory, player):
    """Read-only native identity and state sample; no installation required."""
    ctrl = memory.read_ptr_checked(player + 0x90, 0x68)
    if (memory.read_u32(player) != PLAYER_VTABLE or
            memory.read_u32(ctrl) != CONTROLLER_VTABLE or
            memory.read_u32(ctrl + 4) != player):
        raise MemoryUnavailable('movement controller ownership/vtable mismatch')
    return {'controller': ctrl, 'current_id': memory.read_s32(ctrl + 0x5c),
            'requested_id': memory.read_s32(ctrl + 0x60),
            'controller_vtable': f'0x{CONTROLLER_VTABLE:08X}'}


def configure(memory, snapshot, owned):
    """Host-side data arming ONLY when exact experimental payload installed."""
    from .direct_hooks import plan
    patches = [r for r in plan(include_movement=True) if r[4] == 'movement']
    if len(patches) != 1:
        raise MemoryUnavailable('movement hook not in experimental plan')
    hook, original, arena, payload_bytes, _ = patches[0]
    from .direct_hooks import _branch
    if (memory.read_u32(hook) != _branch(hook, arena) or
            memory.read_bytes(arena, len(payload_bytes))[:4] != payload_bytes[:4]):
        return {'native_gate': 'not installed; default Gecko cannot lock movements'}
    # Authenticate ALL immutable PPC instructions, excluding mutable data words.
    words, _, offset = payload()
    data = arena + offset
    live = bytearray(memory.read_bytes(arena, len(payload_bytes)))
    live[offset:offset+8] = bytes(8)
    if live != payload_bytes:
        raise MemoryUnavailable('movement experiment signature mismatch')
    stage = next(iter(snapshot.evidence.get('native_data', {}).get('stage_objects', [])), {})
    player = stage.get('player', {}).get('actor')
    ctrl = 0
    if (snapshot.scene == 'gameplay' and snapshot.death_state == 'alive'
            and player is not None and snapshot.scene_verified):
        ctrl = observed(memory, player)['controller']
    mask = permissions(owned['counts'])
    # Keep a coherent owner/mask pair. Never tear down an unchanged gate.
    prev, before_mask = memory.read_u32(data), memory.read_u32(data+4)
    if (prev, before_mask) != (ctrl, mask):
        if prev:
            memory.write_u32(data, 0, expected=prev, operation='movement_controls')
        if before_mask != mask:
            memory.write_u32(data+4, mask, expected=before_mask, operation='movement_controls')
        if ctrl:
            memory.write_u32(data, ctrl, expected=0, operation='movement_controls')
    return {'native_gate': 'EXPERIMENTAL guest hook armed' if ctrl else 'not armed outside living gameplay',
            'controller':f'0x{ctrl:08X}' if ctrl else None,'owned_mask':mask,
            'swim_gate':'UNIMPLEMENTED; underwater-specific native transition not verified',
            'breath_gate':'UNIMPLEMENTED; native oxygen counter/reset path not verified',
            'jit_execution_verified':False}
