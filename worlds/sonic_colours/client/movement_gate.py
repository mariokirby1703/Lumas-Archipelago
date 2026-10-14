"""PAL early movement request gate, V11 actor-owned state machine.

800B033C constructs a 0x38-byte ability controller; controller+0x40 is an
unrelated allocation. Resolve the request machine through player+70 -> +8,
with original 80032C9C's vtable and owner at +28. The common dispatcher at
800395B0 gates normal and forced requests before any exit/entry callbacks.
Underwater request 8 uses Swim instead of Double Jump; live validation required.
"""
from .capsule_refresh import PPC
from .memory import MemoryUnavailable, valid_range

# Transient trust is scoped to a verified native C2 data address and a single
# stage epoch. It is not persistent save authority or a substitute for a live
# actor/vtable/back-reference check. This cache is process-local only.
_STABLE_ARM_EPOCH = {}
_STAGE_ARM_OBSERVATIONS = {}  # (stage_epoch, actor, ctrl) -> stable samples

LEGACY_HOOK, LEGACY_ORIGINAL = 0x8003388C, 0x80030020
HOOK = 0x800395B0
ORIGINAL = 0x9421FF40  # stwu r1,-0xC0(r1), common transition dispatcher
CONTROLLER_VTABLE = 0x8075FA3C
STATE_MACHINE_VTABLE = 0x8075A0F8
PLAYER_VTABLE = 0x8075AEF8
# Permission bit 1 = owned/unlocked. State 43 is crouch (first copy),
# state 41 is Slide (second copy). 9 = Jump Dash (user's Mid-Air Boost).
STATE_PERMISSION = {82:13,110:12,29: 9, 30: 10, 38: 7, 8: 0, 9: 1, 10: 1, 13: 2, 39: 3, 40: 3, 41: 4, 43: 5, 44: 6}
CAPABILITY_NAMES = ('Double Jump', 'Mid-Air Boost', 'Homing Attack',
                    'Wall Jump', 'Slide', 'Crouch', 'Stomp', 'Drifting', 'Swim', 'Rail Jump', 'Rail Switch', 'Quick Step', 'Fast Dive', 'Spikes Spin Dash')
DATA_WORDS = 2                 # C2 control + native telemetry; read-only table follows
MENU_POLICY_ARMED = 1  # activation only; current guest owner is resolved natively
MENU_SCENES = ('world_map','global_map','game_land_select')


def permissions(counts):
    """Return native feature mask, NEVER derived from Wisp/normal Boost."""
    return sum(1 << bit for bit, present in enumerate((
        counts['Double Jump'] > 0,
        counts['Mid-Air Boost'] > 0,
        counts['Homing Attack'] > 0,
        counts['Wall Jump'] > 0,
        counts['Progressive Crouch'] >= 2,
        counts['Progressive Crouch'] >= 1,
        counts['Stomp'] > 0,
        counts.get('Drifting', 0) > 0,
        counts.get('Swim', 0) > 0,
        counts.get('Progressive Rail',0)>=1,
        counts.get('Progressive Rail',0)>=2 or counts.get('Rail Switch',0)>0,
        counts.get('Quick Step',0)>0,
        counts.get('Progressive Skydiving',0)>=2,
        counts.get('Progressive Pink Spikes Wisp',0)>=2,
    )) if present)


def payload(gecko=False):
    """Return PPC words, index of deny block and authenticated data offset.

    Control data lives in the same direct-hook allocation. The host writes
    only the exact two-word controller/mask range with compare/readback validation.
    The guest C2 preserves register state while rejecting denied transitions. The hook
    is inert until the host supplies a verified living player's controller.
    """
    a = PPC()
    a.d(37, 1, 1, -0x80)       # stwu r1,-64(r1)
    a.d(47, 9, 1, 8)
    a.d(14,31,3,-0x14)  # common queue receiver -> canonical machine
    # Native 80033890 immediately replaces CR0 with cmpw. All gate
    # comparisons affect only CR0; CR1..7 are untouched. Saved r29 holds LR.
    a.emit(0x7FA802A6)        # mflr r29, restored by lmw at exit
    a.emit(0x48000005)        # bl +4 for PC-relative data, LR restored on exit
    pic_base = len(a.words)*4
    a.emit(0x7D8802A6)        # mflr r12
    # Use PIC base directly; mailbox/table displacements are fixed below.
    a.d(32, 9, 12, 0)          # lwz r9, controller
    a.d(11, 0, 9, 0); a.branch('allow', 0x41820000)
    # Initial activation still requires a host-attributed living Sonic and
    # exact PAL verification. Once active, native machine/player identity and
    # the reverse player+70 -> +8 link follow replacements without a host gap.
    # The nonzero mailbox enables the authenticated AP policy. Resolve each
    # newly constructed native Sonic machine in the guest, before host polling.
    a.d(32, 10, 31, 0)         # verify current guest machine vtable
    a.d(27,10,10,STATE_MACHINE_VTABLE >> 16)
    a.d(10,0,10,STATE_MACHINE_VTABLE & 0xffff); a.branch('allow', 0x40820000)
    a.d(32, 11, 31, 0x28)  # actual native machine owner
    a.d(11, 0, 11, 0); a.branch('allow', 0x41820000)
    a.d(32, 10, 11, 0)
    a.d(27,10,10,PLAYER_VTABLE >> 16)
    a.d(10,0,10,PLAYER_VTABLE & 0xffff); a.branch('allow', 0x40820000)
    a.d(32, 10, 11, 0x70)
    a.d(11, 0, 10, 0); a.branch('allow', 0x41820000)
    a.d(32, 10, 10, 8)
    a.emit(0x7C0AF800); a.branch('allow', 0x40820000)
    # Both 80033878 and forced/repeated 800338E8 reach this call before
    # exit/entry callbacks. Pending -1 is legitimate and never permits bypass.
    # Compact state->permission lookup. Thirteen state entries, padded
    # to a word boundary. Zero denotes an unrestricted native state.
    # Unlike a long chain of comparisons this also restores the Game Land
    # speed-UI C2 in the tightly constrained Gecko codehandler allocation.
    a.d(11,0,4,82);a.branch('spikes_permission',0x41820000)
    a.d(11,0,4,110);a.branch('fast_permission',0x41820000)
    a.label('rail_lookup')
    # Two independent wide permissions: GrindJumpShort 29, GrindJumpSide 30.
    a.d(14,9,4,-29)
    a.d(10,0,9,1);a.branch('table_lookup',0x41810000)
    a.emit(21<<26 | 9<<21 | 9<<16 | 9<<11 | 22<<6 | 31<<1)  # slwi r9,r9,9
    a.d(14,9,9,512)
    # Held actions 2/3, native getter 80056CA0: type 2 -> +4C, bit 2/3.
    # Adding Switch to an explicit Switch request is idempotent; adding it
    # to a directional Jump requires BOTH permissions, not either one.
    a.d(32,10,11,0x88);a.d(32,10,10,0x4c)
    a.d(28,10,10,0xc);a.branch('permission',0x41820000)
    a.d(24,9,9,1024)
    a.branch('permission')
    a.label('table_lookup')
    a.d(14, 9, 4, -8)
    a.d(10, 0, 9, 5); a.branch('lookup', 0x40810000)
    a.d(14, 9, 4, -38)
    a.d(10, 0, 9, 6); a.branch('allow', 0x41810000)
    a.d(14, 9, 9, 6)
    a.label('lookup')
    table_fix = len(a.words)
    a.d(14, 10, 12, 0)
    a.emit(31<<26 | 9<<21 | 10<<16 | 9<<11 | 87<<1)  # lbzx r9,r10,r9
    # Resolve the water bit at request time, never from a stale host poll.
    # r11 still holds the exact authenticated player owner above.
    a.d(11, 0, 4, 8); a.branch('permission', 0x40820000)
    a.d(32, 10, 11, 0x8c)
    a.d(32, 10, 10, 0x10)
    a.d(28, 10, 10, 0x800)  # native water-entry flag, set by 801F0408
    a.branch('permission', 0x41820000)
    a.d(14, 9, 0, 256)       # Swim permission, independent of Double Jump
    a.branch('permission')
    a.label('spikes_permission');a.d(14,9,0,8192);a.branch('permission')
    a.label('fast_permission');a.d(14,9,0,4096)
    a.label('permission')
    a.d(32, 10, 12, 4)         # permissions bitmask
    a.emit(31<<26 | 10<<21 | 10<<16 | 9<<11 | 28<<1 | 1)  # and. r9,r10,r9
    a.emit(0x7C0A4800) # cmpw r10,r9: all requested permission bits required
    a.branch('allow', 0x41820000)
    def restore():
        a.emit(0x7FA803A6) # mtlr r29; lmw restores its original value
        a.d(46, 9, 1, 8)
        a.d(14, 1, 1, 0x80)
    a.label('deny')
    deny_index = len(a.words)
    # Drift/Slide/QuickStep use native Run cleanup; other denied requests
    # return before the common queue creates any exit/entry side effects.
    a.d(28,9,9,0x890)
    a.d(14,4,0,3)
    a.branch('restore',0x41820000)
    a.label('allow')
    a.emit(0x4C421182)  # crclr cr0eq: approved -> native prologue
    a.label('restore')
    restore()
    a.emit(0x4D820020)  # beqlr: denied request, caller's frame untouched
    a.emit(ORIGINAL)
    a.branch('return')
    data_offset = len(a.words)*4
    a.emit(0)                 # controller address, armed LAST
    a.emit(0)                 # independent movement permission mask
    table_offset = len(a.words)*4
    mapping = [1 << STATE_PERMISSION[state] if state in STATE_PERMISSION else 0
               for state in (*range(8,14), *range(38,45))]
    for j in range(0,len(mapping),4):
        a.emit(int.from_bytes(bytes(mapping[j:j+4]).ljust(4,b'\0'),'big'))
    a.label('return')
    if gecko and len(a.words) % 2 == 0:
        a.emit(0x60000000)   # C2 must contain an even number of words
    a.emit(0)                 # filled by Gecko or direct plan (HOOK + 4)
    words = a.finish()
    for i,word in enumerate(words):
        if word>>26 in (32,36) and (word>>16)&31==12:
            words[i]=(word&0xffff0000)|(((word&0xffff)+data_offset-pic_base)&0xffff)
    words[table_fix] |= (table_offset - pic_base) & 0xffff
    return words, deny_index, data_offset


def observed(memory, player):
    """Read-only native identity and state sample; no installation required."""
    ctrl = memory.read_ptr_checked(player + 0x90, 0x38)
    if (memory.read_u32(player) != PLAYER_VTABLE or
            memory.read_u32(ctrl) != CONTROLLER_VTABLE or
            memory.read_u32(ctrl + 4) != player):
        raise MemoryUnavailable('movement controller ownership/vtable mismatch')
    state_owner = memory.read_ptr_checked(player + 0x70, 12)
    machine = memory.read_ptr_checked(state_owner + 8, 0x3c)
    if (memory.read_u32(machine) != STATE_MACHINE_VTABLE
            or memory.read_u32(machine + 0x28) != player
            or memory.read_u32(player + 0x90) != ctrl
            or memory.read_u32(player + 0x70) != state_owner
            or memory.read_u32(state_owner + 8) != machine):
        raise MemoryUnavailable('movement state-machine ownership/vtable mismatch')
    current = memory.read_s32(machine + 0x1c)
    requested = memory.read_s32(machine + 0x20)
    return {'controller': ctrl, 'request_machine':machine,
            'current_id':current, 'requested_id':requested,
            'requested_id_hex':f'0x{requested & 0xFFFFFFFF:08X}',
            'state_fields_plausible':(-1 <= current <= 127 and -1 <= requested <= 127),
            'controller_vtable':f'0x{CONTROLLER_VTABLE:08X}',
            'state_machine_vtable':f'0x{STATE_MACHINE_VTABLE:08X}'}


def _direct_install(memory):
    """Authenticate the previously installed direct hook, if present."""
    from .direct_hooks import plan, _branch
    for hook, original, arena, code, label in plan(include_movement=True):
        if label != 'movement':
            continue
        if memory.read_u32(hook) != _branch(hook, arena):
            return None
        _, _, off = payload()
        live = bytearray(memory.read_bytes(arena, len(code)))
        live[off:off+DATA_WORDS*4] = bytes(DATA_WORDS*4)
        if live != code:
            raise MemoryUnavailable('movement direct payload signature mismatch')
        return arena + off, 'direct RAM (JIT not verified)'
    return None


def _gecko_install(memory):
    from .gecko import inspect_c2
    words,_,off=payload(gecko=True)
    from ..world_constants import load_data
    previous_air=load_data('movement_before_air_boost.json')
    try:
        info=inspect_c2(memory,HOOK,ORIGINAL,{'movement_common_dispatch':words,'movement_before_air_boost':previous_air['words']},((off,8),),label='movement common dispatch')
    except MemoryUnavailable:
        from ..world_constants import load_data
        previous=load_data('movement_before_quick_predicate.json')
        info=inspect_c2(memory,HOOK,ORIGINAL,{'movement_before_quick_predicate':previous['words']},((previous['offset'],8),),label='previous movement dispatcher')
        memory.movement_legacy_profile=True
        return info['target']+previous['offset'],'Dolphin Gecko C2'
    if not info['installed']:return _legacy_gecko_install(memory)
    memory.movement_legacy_profile=info.get('variant')=='movement_before_air_boost'
    return info['target']+off,'Dolphin Gecko C2'



def _legacy_gecko_install(memory):
    """Accept ONLY the exact Dolphin C2 payload with authenticated mutable words."""
    from .gecko import inspect_c2
    from ..world_constants import load_data
    previous=load_data('movement_before_common_dispatch.json')
    words,off=previous['words'],previous['offset']
    try:
        info = inspect_c2(memory, LEGACY_HOOK, LEGACY_ORIGINAL, {'movement_request_gate_v11_owned_machine':words},
                          ((off, DATA_WORDS*4),), label='movement transition')
        memory.movement_legacy_profile = True
    except MemoryUnavailable:
        from ..world_constants import load_data
        previous=load_data('movement_v11_before_spikes_dash.json')
        try:
            info=inspect_c2(memory,HOOK,ORIGINAL,{'movement_before_spikes_dash':previous['words']},
                            ((previous['offset'],8),),label='previous movement without Spikes Spin Dash')
            memory.movement_legacy_profile=True
            return info['target']+previous['offset'],'Dolphin Gecko C2 (update required)'
        except MemoryUnavailable:
            pass
        previous=load_data('movement_v11_no_fast_dive_previous.json')
        try:
            info=inspect_c2(memory,HOOK,ORIGINAL,{'movement_before_fast_dive':previous['words']},
                            ((previous['offset'],8),),label='previous movement without Fast Dive')
            memory.movement_legacy_profile=True
            return info['target']+previous['offset'],'Dolphin Gecko C2 (update required)'
        except MemoryUnavailable:
            pass
        previous=load_data('movement_v11_no_quick_step_previous.json')
        try:
            info=inspect_c2(memory,HOOK,ORIGINAL,{'movement_before_quick_step':previous['words']},
                            ((previous['offset'],8),),label='previous movement without Quick Step')
            memory.movement_legacy_profile=True
            return info['target']+previous['offset'],'Dolphin Gecko C2 (update required)'
        except MemoryUnavailable:
            pass
        previous=load_data('movement_v11_rail_direction_previous.json')
        try:
            info=inspect_c2(memory,HOOK,ORIGINAL,{'movement_rail_direction_previous':previous['words']},
                            ((previous['offset'],8),),label='previous rail gate without directional check')
            memory.movement_legacy_profile=True
            return info['target']+previous['offset'],'Dolphin Gecko C2 (update required)'
        except MemoryUnavailable:
            pass
        previous=load_data('movement_v11_no_rail_switch_previous.json')
        try:
            info=inspect_c2(memory,HOOK,ORIGINAL,{'movement_v11_no_rail_switch':previous['words']},
                            ((previous['offset'],8),),label='previous movement without Rail Switch')
            memory.movement_legacy_profile=True
            return info['target']+previous['offset'],'Dolphin Gecko C2 (update required)'
        except MemoryUnavailable:
            pass
        previous=load_data('movement_v11_no_rail_previous.json')
        try:
            info=inspect_c2(memory,HOOK,ORIGINAL,{'movement_v11_no_rail':previous['words']},
                            ((previous['offset'],8),),label='previous movement without Rail Jump')
            memory.movement_legacy_profile=True
            return info['target']+previous['offset'],'Dolphin Gecko C2 (update required)'
        except MemoryUnavailable:
            pass
        previous=load_data('movement_v11_no_eject_previous.json')
        try:
            info=inspect_c2(memory,HOOK,ORIGINAL,{'movement_v11_no_eject':previous['words']},
                            ((previous['offset'],8),),label='previous movement without ejection')
            memory.movement_legacy_profile=True
            return info['target']+previous['offset'],'Dolphin Gecko C2 (update required)'
        except MemoryUnavailable:
            pass
        previous=load_data('movement_v11_no_drift_previous.json')
        try:
            info=inspect_c2(memory,HOOK,ORIGINAL,{'movement_v11_no_drift':previous['words']},
                            ((previous['offset'],8),),label='previous movement without Drift')
            memory.movement_legacy_profile=True
            return info['target']+previous['offset'],'Dolphin Gecko C2 (update required)'
        except MemoryUnavailable:
            pass
        previous=load_data('movement_v11_follow_previous.json')
        try:
            info=inspect_c2(memory,HOOK,ORIGINAL,{'movement_v11_follow':previous['words']},
                            ((previous['offset'],20),),label='previous follow movement')
            memory.movement_legacy_profile=True
            return info['target']+previous['offset'],'Dolphin Gecko C2 (update required)'
        except MemoryUnavailable:
            pass
        previous=load_data('movement_v11_swim_previous.json')
        try:
            info=inspect_c2(memory,HOOK,ORIGINAL,{'movement_v11_polled_owner':previous['words']},
                            ((previous['offset'],20),),label='polled movement owner')
            memory.movement_legacy_profile=True
            return info['target']+previous['offset'],'Dolphin Gecko C2 (update required)'
        except MemoryUnavailable:
            pass
        previous = load_data('movement_v11_dry_previous.json')
        try:
            info = inspect_c2(memory, LEGACY_HOOK, LEGACY_ORIGINAL, {'movement_v11_dry':previous['words']},
                              ((previous['offset'], 20),), label='dry-only movement transition')
            memory.movement_legacy_profile = True
            return info['target']+previous['offset'], 'Dolphin Gecko C2 (update required)'
        except MemoryUnavailable:
            pass
        previous = load_data('movement_v11_previous.json'); off = previous['offset']
        try:
            info = inspect_c2(memory, LEGACY_HOOK, LEGACY_ORIGINAL, {'movement_request_gate_v11_owned_machine':previous['words']},
                              ((off, 20),), label='previous movement transition')
            memory.movement_legacy_profile = True
        except MemoryUnavailable:
            previous = load_data('movement_v10_previous.json'); off = previous['offset']
            info = inspect_c2(memory, LEGACY_HOOK, LEGACY_ORIGINAL, {'movement_v10_legacy':previous['words']},
                              ((off, previous['data_words']*4),), label='legacy movement transition')
            memory.movement_legacy_profile = True
    if not info['installed']:
        return None
    return info['target'] + off, 'Dolphin Gecko C2'


def installed_data(memory, transport=None):
    """Return (exact data address, transport), or None; never trust an unknown hook."""
    if transport == 'direct':
        return _direct_install(memory)
    if transport == 'gecko':
        return _gecko_install(memory)
    # Probe Gecko first; only the exact recognized bytes may authorize writes.
    try:
        result = _gecko_install(memory)
        if result is not None:
            return result
    except MemoryUnavailable:
        if memory.read_u32(HOOK) == ORIGINAL:
            return None
        # A known direct installation uses a different signature. Try that.
    return _direct_install(memory)


def gecko_lines():
    words, _, _ = payload(gecko=True)
    assert len(words) % 2 == 0 and words[-1] == 0
    return ([f'20{HOOK-0x80000000:06X} {ORIGINAL:08X}',
             f'C2{HOOK-0x80000000:06X} {len(words)//2:08X}'] +
            [f'{words[i]:08X} {words[i+1]:08X}' for i in range(0,len(words),2)])


def configure(memory, snapshot, owned, transport=None):
    """Arm an exact recognized guest hook for a verified living PAL Sonic actor.

    Bound map scenes can preload policy before the next actor is constructed.
    The guest treats the mailbox as activation and independently verifies its
    current machine/player/reverse link on every request. No stale host pointer
    is dereferenced. The owner is cleared BEFORE mask changes and armed LAST.
    No effect is
    claimed if the native gate has not demonstrably run in Dolphin gameplay.
    """
    match = installed_data(memory, transport)
    if match is None:
        return {'status': 'movement C2 not installed', 'native_gate_verified': False,
                'swim_gate_verified': False, 'breath_gate_verified': False}
    data, method = match
    if getattr(memory, 'movement_legacy_profile', False):
        return {'status':'Update complete Gecko profile: installed payload lacks current movement permissions (Quick Step/Rail)', 'native_gate_verified':False}
    stage = next(iter(snapshot.evidence.get('native_data', {}).get('stage_objects', [])), {})
    player = stage.get('player', {}).get('actor')
    ctrl = 0
    controller_reason = 'awaiting stable attributed native gameplay actor'
    prior_ctrl = memory.read_u32(data)
    prior_epoch = _STABLE_ARM_EPOCH.get(data)
    transient_grace = False
    stage_epoch = snapshot.stage_epoch
    menu_preload = (snapshot.scene in MENU_SCENES and snapshot.scene_verified
                    and snapshot.stable_polls >= 1)
    same_stage = bool(prior_epoch and prior_epoch[0] == stage_epoch)
    if (same_stage and snapshot.scene_verified and snapshot.scene == 'gameplay'
            and player is None):
        # A secondary stats/actor scan can miss a moving actor for one sample.
        # This authorizes NO host writes and makes no cached actor claim. The
        # already installed guest gate independently rechecks machine + owner
        # each request. Do not erase the stage-local proof because of this scan.
        return {'status':'movement update deferred: secondary player read unavailable in the same stage',
                'native_gate_verified':False, 'installed_signature_verified':True,
                'transport':method, 'host_writes_deferred':True}
    if (snapshot.scene == 'gameplay' and snapshot.death_state == 'alive'
            and snapshot.scene_verified and snapshot.stable_polls >= 1
            and stage_epoch is not None and player is not None):
        candidate = observed(memory, player)  # ALWAYS revalidate actor and back-reference
        current, requested = candidate['current_id'], candidate['requested_id']
        valid_pending = 0 <= requested <= 127
        key = (stage_epoch, player, candidate['request_machine'])
        prior = _STAGE_ARM_OBSERVATIONS.get(data)
        # Actor/vtable/backref is re-verified by observed() on EVERY poll.
        # Stage-local state-ID snapshots are secondary diagnostics only:
        # after Act1 they can contain pointer words, even when the player
        # and the controller backreference are otherwise valid. The exact
        # native ownership chain is sufficient on the first verified sample.
        # The guest independently rejects invalid native r3+0x20 requests.
        host_fields_plausible = (-1 <= current <= 127 and valid_pending)
        already_attributed = prior_epoch == key
        required_samples = 1
        seen = prior[1] + 1 if prior and prior[0] == key else 1
        if prior and prior[0] != key:
            _STABLE_ARM_EPOCH.pop(data, None)
        _STAGE_ARM_OBSERVATIONS[data] = (key, seen)
        if already_attributed or seen >= required_samples:
            ctrl = candidate['request_machine']
            _STABLE_ARM_EPOCH[data] = key
            transient_grace = (current == -1 and valid_pending)
            controller_reason = ('stable host fields and native guest guard' if host_fields_plausible
                                 else 'actor/backreference stable; native guest request guard active (host state IDs unreliable)')
        else:
            controller_reason = f'awaiting native controller stage rearm ({seen}/{required_samples})'
    if menu_preload:
        ctrl = MENU_POLICY_ARMED
        controller_reason = 'bound map policy preloaded; guest resolves next living owner'
    if not ctrl or menu_preload:
        # Only transient -1 samples from the SAME previously stable stage may
        # retain grace; otherwise stale epoch trust must be forgotten.
        if not controller_reason.startswith('awaiting native controller stage rearm'):
            _STABLE_ARM_EPOCH.pop(data, None)
            _STAGE_ARM_OBSERVATIONS.pop(data, None)
    mask = permissions(owned['counts'])
    from .skydiving import configure as configure_skydiving
    try:
        skydiving = configure_skydiving(memory,snapshot,owned) if ctrl else {'status':'awaiting living movement owner'}
    except MemoryUnavailable as error:
        skydiving = {'status':str(error),'installed':False}
    before_ctrl, before_mask = prior_ctrl, memory.read_u32(data+4)
    if (before_ctrl, before_mask) != (ctrl, mask):
        if before_ctrl:
            memory.write_u32(data, 0, expected=before_ctrl, operation='movement_controls')
        if before_mask != mask:
            memory.write_u32(data+4, mask, expected=before_mask, operation='movement_controls')
        if ctrl:
            memory.write_u32(data, ctrl, expected=0, operation='movement_controls')
    # Runtime telemetry from the guest hook, never a substitute for a live
    # end-to-end ability/animation test. Only read after exact payload verification.
    denied_count, last_denied = 0, 0
    return {'status': 'armed native movement request-gate V11 native state-machine guarded via '+method if ctrl else 'movement hook fail-open: '+controller_reason,
            'skydiving':skydiving,
            'native_gate_verified': False, 'installed_signature_verified': True, 'transport': method,
            'request_machine':f'0x{ctrl:08X}' if ctrl and not menu_preload else None,
            'controller':f'0x{stage.get("player",{}).get("movement",{}).get("controller",0):08X}' if ctrl and not menu_preload else None, 'owned_mask':mask,
            'menu_policy_preloaded':menu_preload,
            'denied_transition_count':denied_count,
            'last_denied_state':last_denied if denied_count else None,
            'guest_denial_counter_nonzero':bool(denied_count),
            'controller_identity_mode': 'guest_player_vtable_and_player70_owner8_reverse_link',
            'transient_minus_one_grace_active': transient_grace,
            'controller_arm_reason':controller_reason,
            'stage_controller_consecutive_samples': _STAGE_ARM_OBSERVATIONS.get(data, (None,0))[1],
            'native_request_source': 'common PAL queue r3-0x14; normal and forced requests gated before callbacks',
            'same_stage_authorization_retained':bool(prior_epoch and ctrl and prior_epoch == (stage_epoch, player, ctrl)),
            'host_controller_state_fields_reliable': bool(player is not None and stage.get('player',{}).get('movement',{}).get('state_fields_plausible')),
            'swim_gate_verified': False, 'breath_gate_verified': False,
            'native_execution_confirmed': False}


def water_observed(memory, player):
    """Read-only water research. NEVER authorize oxygen writes from this data."""
    import struct
    stats = memory.read_ptr_checked(player + 0x8c, 0x3c)
    if memory.read_u32(stats) != 0x8075E088:
        raise MemoryUnavailable('water probe: player stats vtable mismatch')
    flag_a,flag_b,flag_c = (memory.read_u32(stats+offset) for offset in (8,12,16))
    result = {'stats_flags_a': f'0x{flag_a:08X}',
              'stats_flags_b': f'0x{flag_b:08X}',
              'stats_flags_c': f'0x{flag_c:08X}',
              'underwater_combined_bits_observed': bool((flag_c & 0x00200800)==0x00200800),
              'jump_airborne_bit_observed': bool(flag_a & 0x100),
              'jump_variant_observed':memory.read_u32(stats+0x1c),
              'candidate_proven_oxygen_timer': False}
    try:
        from .water_native import read as read_oxygen
        result['native_oxygen']=read_oxygen(memory,player)
        result['candidate_proven_oxygen_timer']=True
    except MemoryUnavailable as error:
        result['native_oxygen']={'status':str(error),'write_verified':False}
    # The proximity to an owned plugin is useful observational evidence only.
    # Nothing establishes that plugin-0x30 belongs to the same allocation.
    try:
        plugin = memory.read_ptr_checked(player + 0x94, 8)
        if memory.read_u32(plugin) == 0x8075FEB8 and memory.read_u32(plugin+4)==player and valid_range(plugin-0x30,4):
            val=memory.read_f32(plugin-0x30)
            result['unverified_plugin_minus_0x30_float']=val
            result['unverified_float_note']='Not authorized as a breath timer; likely separate allocation/visual clock'
    except MemoryUnavailable:
        pass
    return result
