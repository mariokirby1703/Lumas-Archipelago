"""Experimental in-memory CSB BGM rewriting, no CPK or Gecko required.

The ORIGINAL PAL CSB bank was verified byte-for-byte in independent supplied
MEM2 captures at 0x9017E8A0. That address is a *hint*, not a trusted pointer.
Only a bank whose complete immutable content can be reconstructed/verified from
the trusted original hash is writable. Validated SYNTH audio leaf references change.
Guest code and Dolphin JIT state are never modified by this module.
"""
import hashlib
import struct
from .memory import MemoryUnavailable, valid_range
from .music_bank import CATALOG, CUES, WISP_CUES, FINITE_CUES, SHUFFLE_CUES, plan, slot_plan, rewrite_bank, recover_bank
from .cpk import UTF

ORIGINAL_SHA256 = CATALOG['bank_sha256']
# Exact original bank size from multiple independent PAL memory captures.
ORIGINAL_SIZE = 0x137A8
CANDIDATE_POINTERS = (0x80B3ECD8, 0x80B3ECDC)
CANDIDATE_HINTS = (0x9017E8A0,)


def recover_original(raw):
    """Reconstruct the PAL original using immutable CSB string identities.

    Reject a candidate if anything besides authenticated audio leaf references
    (or exact legacy compatible CUE redirects) differs.
    A damaged/corrupt bank must never become writable merely because it starts
    with @UTF or contains familiar names.
    """
    if len(raw) != ORIGINAL_SIZE:
        raise MemoryUnavailable('music bank has unsupported PAL length')
    try:
        return recover_bank(raw)
    except (ValueError, TypeError, KeyError, StopIteration, IndexError, struct.error) as error:
        raise MemoryUnavailable(f'music bank original identity could not be proven: {error}') from error


def probe_bank(memory):
    """Read-only, bounded candidate lookup. No unvalidated heap address writes."""
    candidates = list(CANDIDATE_HINTS)
    for ptr in CANDIDATE_POINTERS:
        try:
            target = memory.read_u32(ptr)
            if target not in candidates:
                candidates.append(target)
        except MemoryUnavailable:
            pass
    for address in candidates:
        if address % 4 or not valid_range(address, ORIGINAL_SIZE):
            continue
        try:
            original_or_patched = memory.read_bytes(address, ORIGINAL_SIZE)
            if hashlib.sha256(original_or_patched).hexdigest() == ORIGINAL_SHA256:
                return address, original_or_patched, original_or_patched
            canonical = recover_original(original_or_patched)
            return address, original_or_patched, canonical
        except MemoryUnavailable:
            continue
    raise MemoryUnavailable('music: original PAL in-memory BGM bank not at verified candidate addresses')


def apply(memory, slot, test_pair=None):
    """Apply/restore a global audio-content permutation in the resident CSB.

    This changes loaded data. Whether CRI has cached the currently playing cue
    must still be verified audibly after cue restart/scene transition.
    """
    base, current, original = probe_bank(memory)
    on = bool(slot['options']['music_randomization'])
    mapping = slot_plan(slot)
    if test_pair is not None:
        destination,donor=test_pair
        if not on or destination not in SHUFFLE_CUES or donor not in (SHUFFLE_CUES | {'bgm_sys_op','bgm_sys_end'}):
            raise MemoryUnavailable('music test requires a looping destination and an eligible donor with Music Randomization On; other finite cues stay vanilla')
        if donor in ('bgm_sys_op','bgm_sys_end'):
            mapping[destination]=donor # retain original opening/credits audio
        else:
            owner=next((name for name,value in mapping.items() if value==donor),None)
            if owner is None:mapping[destination]=donor
            else:mapping[owner],mapping[destination]=mapping[destination],mapping[owner]
    replacement = rewrite_bank(original, mapping, finite_audition=test_pair is not None,mapping_version=slot.get('music_mapping_version',1))
    if current != replacement:
        memory._music_bank_transaction = (base, hashlib.sha256(current).hexdigest(),
                                          hashlib.sha256(replacement).hexdigest())
        try:
            memory.write_bytes_verified(base, replacement, expected=current, operation='music_bank')
        finally:
            memory._music_bank_transaction = None
    return {'status': 'verified PAL BGM bank rewritten in Wii MEM2' if current != replacement else
                       'verified PAL BGM bank already matches this seed',
            'bank_address':f'0x{base:08X}', 'scope':'one global pool / destination control graphs retained',
            'strategy':'destination_graph_audio_leaves_v1',
            'music_mapping_version':slot.get('music_mapping_version',1),
            'pool_size':len(SHUFFLE_CUES)+(2 if slot.get('music_mapping_version',1)==2 else 0), 'excluded_cues':sorted(FINITE_CUES),
            'transformation_cues':sorted(WISP_CUES),
            'excluded_finite_tracks':sorted(FINITE_CUES-({'bgm_sys_op','bgm_sys_end'} if slot.get('music_mapping_version',1)==2 else set())),
            'finite_audio_destinations':{n:d for n,d in mapping.items() if n != d and d in FINITE_CUES},
            'duration_validation':('vanilla bank restored; no shuffled duration adaptation' if not on else
                'native full-song replay for opening/credits donors; original finite destinations retained'
                if slot.get('music_mapping_version',1)==2 or test_pair and test_pair[1] in ('bgm_sys_op','bgm_sys_end')
                else 'legacy looping-only mapping'),
            'wisp_music_mapping':{n:mapping[n] for n in sorted(WISP_CUES)},
            'test_pair':test_pair,
            'randomized_cues':sum(name!=donor for name,donor in mapping.items()),
            'seed':slot['seed_name'],'audible_verified':False,
            'note':'Existing playing cues may require a menu/stage transition before new synth selection'}


def finite_loop_policy(memory):
    """Prove the *resident* destination uses one of the two finite songs.

    Original opening/credits destinations are deliberately ineligible even if
    their audio is remapped. No duration timer or host audio-start call is used.
    """
    from . import native_events as n
    from .music_bank import GRAPHS
    event=n.status(memory)
    name=event['cue_name']
    if (name not in SHUFFLE_CUES or CUES[name]['id']!=event['cue_id']
            or not 0<event['cue_id']<=0xffff):
        return 0
    _,raw,_=probe_bank(memory)
    leaves=GRAPHS['graphs'][name]
    observed=tuple(struct.unpack_from('>I',raw,leaf['cell'])[0] for leaf in leaves)
    for donor in ('bgm_sys_op','bgm_sys_end'):
        source=GRAPHS['graphs'][donor]
        expected=tuple(source[min(i,len(source)-1)]['original_ref'] for i in range(len(leaves)))
        if observed==expected:return event['cue_id']
    return 0


def configure_finite_loop(memory):
    from . import native_events as n
    base=n.address(memory);value=finite_loop_policy(memory)
    before=memory.read_bytes(base+n.LOOP_CUE,4);raw=struct.pack('>I',value)
    # Upper bits belong to the game-thread replay latch. Preserve them for
    # the same cue; only a changed/disabled destination resets the latch.
    same_policy=value!=0 and (int.from_bytes(before,'big')&0xffff)==value
    if before!=raw and not same_policy:
        memory._event_transaction={'music_loop':True,'value':value,'allowed':{base+n.LOOP_CUE:4}}
        try:memory.write_bytes_verified(base+n.LOOP_CUE,raw,expected=before,operation='native_event_controls')
        finally:memory._event_transaction=None
    return {'eligible_cue_id':value,'strategy':'native stopped-state restart','loop_live_verified':False}
