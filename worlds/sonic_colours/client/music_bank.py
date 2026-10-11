"""Seed-aware PAL BGM cue redirects in a separate original-data CPK copy.

Cue IDs, names, flags, timing/control graphs and audio bytes stay intact. Only
the cue's synth reference changes to a compatible, existing BGM synth. Timed
opening/ending music, transformation cues and critical jingles are protected.
"""
import hashlib
import json
import random
from pathlib import Path
from ..world_constants import load_data
from .cpk import CPK, UTF

CATALOG = load_data('bgm_cues.json')
CUES = {row['name']: row for row in CATALOG['cues']}
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
        key = json.dumps(row['compatibility']), group(name) if mode == 'per_world' else 'global'
        groups.setdefault(key, []).append(name)
    rng = random.Random(int.from_bytes(hashlib.sha256(f'{seed}:sonic-bgm-bank-v1'.encode()).digest(), 'big'))
    for key in sorted(groups):
        names = sorted(groups[key]); donors = names.copy(); rng.shuffle(donors)
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
        if ((name in PROTECTED and donor != name) or donor in PROTECTED and donor != name
                or source['compatibility'] != target['compatibility']):
            raise ValueError('incompatible or protected BGM redirect')
        i, j = indices[name], indices[donor]
        for key in ('id', 'flags', 'synth'):
            if cue.rows[i][key] != source[key]: raise ValueError('PAL cue identity mismatch')
        position, fmt = cue.cells[i]['synth']
        donor_position, donor_fmt = cue.cells[j]['synth']
        if position is None or donor_position is None or fmt != '>I' or donor_fmt != fmt:
            raise ValueError('PAL cue synth field is not independently writable')
        output[base+position:base+position+4] = original[base+donor_position:base+donor_position+4]
    verify = UTF(bytes(output)[base:base+size])
    for row in verify.rows:
        if row['synth'] != CUES[mapping[row['name']]]['synth']:
            raise ValueError('BGM synth redirect readback mismatch')
    return bytes(output)


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
    bank = UTF(data)
    offset, size = next(row['utf'] for row in bank.rows if row['name'] == 'CUE')
    base = bank.binary + offset; cue = UTF(data[base:base+size])
    if len(cue.rows) != len(CUES): raise ValueError('resource cue catalog mismatch')
    original = bytearray(data)
    for i, row in enumerate(cue.rows):
        if row['name'] not in CUES: raise ValueError('unknown resource BGM cue')
        position, fmt = cue.cells[i]['synth']
        if position is None or fmt != '>I': raise ValueError('resource synth layout mismatch')
        # Recover the original reference from the unchanged string pool. The
        # original bank hash then verifies ALL unrelated fields and graphs.
        string = CUES[row['name']]['synth'].encode()+b'\0'
        original_offset = cue.data.index(string, cue.strings, cue.binary)-cue.strings
        original[base+position:base+position+4] = original_offset.to_bytes(4, 'big')
    if rewrite_bank(bytes(original), mapping) != data:
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
            'seed': manifest['seed'], 'scope': 'compatible_bgm_bank', 'runtime_cue_policy': 'original',
            'resource_verified': True, 'audible_verified': False}
