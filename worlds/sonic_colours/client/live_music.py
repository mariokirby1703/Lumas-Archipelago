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
from .music_bank import CATALOG, CUES, PROTECTED, WISP_CUES, plan, rewrite_bank, recover_bank
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
    mapping = plan(slot['seed_name'], 'anywhere' if on else 'off')
    if test_pair is not None:
        destination,donor=test_pair
        if not on or destination in PROTECTED or donor in PROTECTED or destination not in CUES or donor not in CUES:
            raise MemoryUnavailable('music test requires two eligible cues and Music Randomization On')
        owner=next(name for name,value in mapping.items() if value==donor)
        mapping[owner],mapping[destination]=mapping[destination],mapping[owner]
    replacement = rewrite_bank(original, mapping)
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
            'protected_cues':sorted(PROTECTED),
            'transformation_cues':sorted(WISP_CUES),
            'finite_audio_donors':['bgm_pha_rkt'],
            'finite_audio_destinations':[n for n,d in mapping.items() if d == 'bgm_pha_rkt'],
            'wisp_music_mapping':{n:mapping[n] for n in sorted(WISP_CUES)},
            'test_pair':test_pair,
            'randomized_cues':sum(name!=donor for name,donor in mapping.items()),
            'seed':slot['seed_name'],'audible_verified':False,
            'note':'Existing playing cues may require a menu/stage transition before new synth selection'}
