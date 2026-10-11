"""Global PAL audio-content shuffle retaining each destination's control graph.

Change only leaf AAX references in the resident CSB. Cue identity, native filter,
boost/sleep graphs, audio bytes and synchronized/critical music remain intact.
"""
import hashlib
import json
import random
import struct
from pathlib import Path
from ..world_constants import load_data
from .cpk import CPK, UTF

CATALOG = load_data('bgm_cues.json')
CUES = {row['name']: row for row in CATALOG['cues']}
AUDIO = load_data('bgm_audio_identity.json')
GRAPHS = load_data('bgm_graphs.json')
if GRAPHS['bank_sha256'] != CATALOG['bank_sha256'] or set(GRAPHS['graphs']) != set(CUES):
    raise ValueError('PAL BGM graph catalog mismatch')
if AUDIO['bank_sha256'] != CATALOG['bank_sha256'] or set(AUDIO['cues']) != set(CUES):
    raise ValueError('PAL audio identity catalog mismatch')
PROTECTED = frozenset(name for name in CUES if name.startswith(('bgm_jingle_', 'bgm_pha_'))
                      or name in ('bgm_sys_theme', 'bgm_sys_op', 'bgm_sys_end'))


def group(name):
    if name.startswith('bgm_stg'): return 'stage_' + name.rsplit('_', 1)[1]
    if name.startswith('bgm_boss_'): return 'boss'
    if name in {f'bgm_mlt_{letter}' for letter in 'abcdefg'}: return 'game_land'
    if name == 'bgm_wmap' or name.startswith('bgm_zmap_'): return 'maps'
    return 'menus'


def plan(seed, mode):
    if mode not in ('off', 'per_world', 'anywhere') or not isinstance(seed, str) or not seed:
        raise ValueError('BGM bank requires a seed and supported music mode')
    result = {name: name for name in CUES}
    if mode == 'off': return result
    groups = {}
    for name, row in CUES.items():
        if name in PROTECTED: continue
        key = group(name) if mode == 'per_world' else 'global'
        groups.setdefault(key, []).append(name)
    rng = random.Random(int.from_bytes(hashlib.sha256(f'{seed}:sonic-bgm-bank-v1'.encode()).digest(), 'big'))
    for key in sorted(groups):
        names = sorted(groups[key]); donors = names.copy(); rng.shuffle(donors)
        # Eliminate self-maps without retry loops or a biased fallback seed.
        fixed = [i for i, (name, donor) in enumerate(zip(names, donors)) if name == donor]
        if len(names) > 1:
            if len(fixed) == 1:
                i = fixed[0]; j = (i + 1) % len(names)
                donors[i], donors[j] = donors[j], donors[i]
            elif fixed:
                original_fixed = [donors[i] for i in fixed]
                for i, donor in zip(fixed, original_fixed[1:] + original_fixed[:1]): donors[i] = donor
        # Distinct cues can be aliases of the very same AAX music (Aquarium
        # Acts 1/4, 2/5 and 3/6). Find a seeded perfect matching by audio identity.
        choices = {n: [d for d in donors if AUDIO['cues'][n] != AUDIO['cues'][d]] for n in names}
        assigned = {}
        def assign(name, seen):
            for donor in choices[name]:
                if donor in seen: continue
                seen.add(donor)
                if donor not in assigned or assign(assigned[donor], seen):
                    assigned[donor] = name
                    return True
            return False
        if all(assign(n, set()) for n in names):
            result.update({name: donor for donor, name in assigned.items()})
        else:
            result.update(zip(names, donors))
    return result


def rewrite_bank(original, mapping):
    if hashlib.sha256(original).hexdigest() != CATALOG['bank_sha256']:
        raise ValueError('original PAL BGM bank SHA256 mismatch')
    if set(mapping) != set(CUES) or any(donor not in CUES for donor in mapping.values()):
        raise ValueError('BGM mapping must cover exactly the original cue catalog')
    bank = UTF(original)
    offset, size = next(row['utf'] for row in bank.rows if row['name'] == 'CUE')
    base = bank.binary + offset; cue = UTF(original[base:base+size])
    indices = {row['name']: i for i, row in enumerate(cue.rows)}
    if len(indices) != len(CUES) or set(indices) != set(CUES):
        raise ValueError('PAL BGM cue layout mismatch')
    output = bytearray(original)
    for name, donor in mapping.items():
        source, target = CUES[name], CUES[donor]
        if ((name in PROTECTED and donor != name) or donor in PROTECTED and donor != name):
            raise ValueError('incompatible or protected BGM redirect')
        i, j = indices[name], indices[donor]
        for key in ('id', 'flags', 'synth'):
            if cue.rows[i][key] != source[key]: raise ValueError('PAL cue identity mismatch')
        # Keep the destination's root, ISAAC control graph and every DSP field.
        # A one-leaf destination plays the donor's normal audio; a two-leaf
        # destination retains normal/fx control, duplicating a single donor
        # reference where the source has no separate boost audio stem.
        destination = GRAPHS['graphs'][name]
        audio = GRAPHS['graphs'][donor]
        for k, leaf in enumerate(destination):
            pos = leaf['cell']
            if struct.unpack_from('>I', original, pos)[0] != leaf['original_ref']:
                raise ValueError('PAL synth leaf layout mismatch')
            reference = audio[min(k, len(audio)-1)]['original_ref']
            struct.pack_into('>I', output, pos, reference)
    if recover_bank(bytes(output)) != original:
        raise ValueError('BGM graph adaptation readback mismatch')
    return bytes(output)


def recover_bank(data):
    """Validate either exact legacy cue redirects or current audio-leaf edits.

    Reconstruct ALL allowed cells, hash every immutable byte, then prove that
    each destination's leaf vector comes from one eligible donor. Unknown refs,
    damaged graphs, protected edits and mixed legacy/current layouts are rejected.
    """
    outer = UTF(data)
    offset, size = next(r['utf'] for r in outer.rows if r['name'] == 'CUE')
    base = outer.binary + offset; cues = UTF(data[base:base+size])
    if len(cues.rows) != len(CUES) or {r['name'] for r in cues.rows} != set(CUES):
        raise ValueError('unknown CUE catalog')
    original = bytearray(data); cue_changed = False; leaves_changed = False
    donors = {r['synth']:r for r in CUES.values()}
    for row, cells in zip(cues.rows,cues.cells):
        source=CUES[row['name']]; donor=donors.get(row['synth'])
        if not donor or (row['synth'] != source['synth'] and
                (row['name'] in PROTECTED or donor['name'] in PROTECTED or
                 source['compatibility'] != donor['compatibility'])):
            raise ValueError('invalid legacy CUE redirect')
        cue_changed |= row['synth'] != source['synth']
        pos,fmt=cells['synth']
        if pos is None or fmt != '>I': raise ValueError('invalid CUE cell')
        ref=cues.data.index(source['synth'].encode()+b'\0',cues.strings,cues.binary)-cues.strings
        struct.pack_into('>I',original,base+pos,ref)
    for name, leaves in GRAPHS['graphs'].items():
        observed=tuple(struct.unpack_from('>I',data,leaf['cell'])[0] for leaf in leaves)
        expected=tuple(leaf['original_ref'] for leaf in leaves)
        leaves_changed |= observed != expected
        allowed = (name,) if name in PROTECTED else tuple(n for n in CUES if n not in PROTECTED)
        if not any(observed == tuple(GRAPHS['graphs'][d][min(k,len(GRAPHS['graphs'][d])-1)]['original_ref']
                                     for k in range(len(leaves))) for d in allowed):
            raise ValueError('invalid or mixed donor audio leaves')
        for leaf in leaves: struct.pack_into('>I',original,leaf['cell'],leaf['original_ref'])
    if cue_changed and leaves_changed: raise ValueError('mixed legacy and graph audio redirects')
    if hashlib.sha256(original).hexdigest() != CATALOG['bank_sha256']:
        raise ValueError('CSB differs beyond authorized music fields')
    return bytes(original)


def patch(source, output, seed, mode):
    from .asset_patch import PAL_CPK_SHA256
    if mode == 'off': raise ValueError('Music Randomization is off')
    output = Path(output); manifest_path = Path(str(output) + '.json')
    if manifest_path.exists(): raise ValueError('output manifest already exists')
    archive = CPK(source)
    indices = [i for i, r in enumerate(archive.toc.rows) if r['DirName'] == 'sound' and r['FileName'] == 'bgm.strm.csb']
    if len(indices) != 1: raise ValueError('original PAL BGM member not unique')
    index = indices[0]; original = archive.read(archive.toc.rows[index])
    mapping = plan(seed, mode); replacement = rewrite_bank(original, mapping)
    archive.replace_member(output, index, replacement, PAL_CPK_SHA256)
    manifest = {'format': 'sonic-pal-bgm-bank-v1', 'seed': seed, 'mode': mode,
                'source_cpk_sha256': PAL_CPK_SHA256, 'resource_file': output.name,
                'original_bank_sha256': CATALOG['bank_sha256'],
                'patched_bank_sha256': hashlib.sha256(replacement).hexdigest(),
                'music_mapping': mapping, 'protected_cues': sorted(PROTECTED),
                'runtime_cue_policy': 'original', 'audible_verified': False}
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    return manifest


def validate_resource_bank(data, mapping):
    if rewrite_bank(recover_bank(data), mapping) != data:
        raise ValueError('resource bank differs from the seed redirects')


def load_manifest(path, slot):
    """Validate an explicitly selected resource patch, never infer installation."""
    path = Path(path); manifest = json.loads(path.read_text(encoding='utf-8'))
    mode = 'anywhere' if slot['options']['music_randomization'] else 'off'
    if (manifest.get('format') != 'sonic-pal-bgm-bank-v1' or manifest.get('seed') != slot['seed_name']
            or manifest.get('mode') != mode or mode == 'off'
            or manifest.get('music_mapping') != plan(slot['seed_name'], mode)
            or manifest.get('runtime_cue_policy') != 'original'):
        raise ValueError('music resource manifest does not match the authenticated seed/mode')
    name = manifest.get('resource_file')
    if not isinstance(name, str) or Path(name).name != name:
        raise ValueError('music resource must be beside its manifest')
    archive = CPK(path.parent/name)
    rows = [r for r in archive.toc.rows if r['DirName'] == 'sound' and r['FileName'] == 'bgm.strm.csb']
    if len(rows) != 1:
        raise ValueError('selected music resource bank is not unique')
    data = archive.read(rows[0])
    if hashlib.sha256(data).hexdigest() != manifest.get('patched_bank_sha256'):
        raise ValueError('selected music resource bank does not match its manifest')
    validate_resource_bank(data, manifest['music_mapping'])
    return {'status': 'seed resource verified on disk; loaded Dolphin resource and playback unverified',
            'seed': manifest['seed'], 'scope': 'global_audio_content_bank', 'runtime_cue_policy': 'original',
            'resource_verified': True, 'audible_verified': False}
