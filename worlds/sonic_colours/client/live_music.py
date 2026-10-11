"""Experimental in-memory CSB BGM rewriting, no CPK or Gecko required.

The ORIGINAL PAL CSB bank was verified byte-for-byte in independent supplied
MEM2 captures at 0x9017E8A0. That address is a *hint*, not a trusted pointer.
Only a bank whose complete immutable content can be reconstructed/verified from
the trusted original hash is writable. Only validated CUE synth references change.
Guest code and Dolphin JIT state are never modified by this module.
"""
import hashlib
import struct
from .memory import MemoryUnavailable, valid_range
from .music_bank import CATALOG, CUES, PROTECTED, plan, rewrite_bank
from .cpk import UTF

ORIGINAL_SHA256 = CATALOG['bank_sha256']
# Exact original bank size from multiple independent PAL memory captures.
ORIGINAL_SIZE = 0x137A8
CANDIDATE_POINTERS = (0x80B3ECD8, 0x80B3ECDC)
CANDIDATE_HINTS = (0x9017E8A0,)


def recover_original(raw):
    """Reconstruct the PAL original using immutable CSB string identities.

    Reject a candidate if *anything* besides compatible CUE synth words differs.
    A damaged/corrupt bank must never become writable merely because it starts
    with @UTF or contains familiar names.
    """
    if len(raw) != ORIGINAL_SIZE:
        raise MemoryUnavailable('music bank has unsupported PAL length')
    try:
        outer = UTF(raw)
        offset, size = next(r['utf'] for r in outer.rows if r['name'] == 'CUE')
        base = outer.binary + offset
        cues = UTF(raw[base:base+size])
        if len(cues.rows) != len(CUES) or {r['name'] for r in cues.rows} != set(CUES):
            raise ValueError('unknown CUE catalog')
        output = bytearray(raw)
        groups = {name: row['compatibility'] for name, row in CUES.items()}
        donors = {row['synth']: row for row in CUES.values()}
        for row, cells in zip(cues.rows, cues.cells):
            name = row['name']
            source = CUES[name]
            donor = donors.get(row['synth'])
            if not donor or groups[name] != donor['compatibility']:
                raise ValueError('CSB synth from incompatible donor')
            if name in PROTECTED and row['synth'] != source['synth']:
                raise ValueError('protected cue was changed')
            pos, fmt = cells['synth']
            if pos is None or fmt != '>I':
                raise ValueError('no mutable synth CUE field')
            original_ref = source['synth'].encode('utf-8') + b'\0'
            synth_offset = cues.data.index(original_ref, cues.strings, cues.binary) - cues.strings
            struct.pack_into('>I', output, base+pos, synth_offset)
        if hashlib.sha256(output).hexdigest() != ORIGINAL_SHA256:
            raise ValueError('CSB differs beyond authorized CUE synth fields')
        return bytes(output)
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


def apply(memory, slot):
    """Apply/restore a compatible permutation directly in the resident CSB.

    This changes loaded data. Whether CRI has cached the currently playing cue
    must still be verified audibly after cue restart/scene transition.
    """
    base, current, original = probe_bank(memory)
    on = bool(slot['options']['music_randomization'])
    mapping = plan(slot['seed_name'], 'anywhere' if on else 'off')
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
            'bank_address':f'0x{base:08X}', 'scope':'87 original cues / compatible synth groups',
            'randomized_cues':sum(name!=donor for name,donor in mapping.items()),
            'seed':slot['seed_name'],'audible_verified':False,
            'note':'Existing playing cues may require a menu/stage transition before new synth selection'}
