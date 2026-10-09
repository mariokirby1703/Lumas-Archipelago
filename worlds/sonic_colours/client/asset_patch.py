"""Apply a seed's actual music redirects to a separate player-owned PAL CPK."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from .audio import plan_music
from .cpk import CPK, UTF
from ..world_constants import NORMAL


PAL_CPK_SHA256 = '58bbf2be97a2f08effb5752bd40eea8a1ba76a18349937a32351624d855651bf'
NAME = re.compile(rb'\bname\s*=\s*"(stg[0-9A-G][0-9]{2})"')
BGM = re.compile(rb'\bbgm\s*=\s*"([A-Za-z0-9_]+)"')


def replace_music(script, mapping):
    """Preserve the original script bytes, spawn data and all unrelated fields."""
    entries = list(NAME.finditer(script))
    edits, found = [], set()
    original = {stage['mission_id']: stage['bgm'] for stage in NORMAL}
    if set(mapping) != set(original):
        raise ValueError('music mapping must cover precisely the 36 normal acts')
    for index, entry in enumerate(entries):
        mission = entry[1].decode('ascii')
        if mission not in mapping:
            continue
        end = entries[index + 1].start() if index + 1 < len(entries) else len(script)
        matches = list(BGM.finditer(script, entry.end(), end))
        if mission in found or len(matches) != 1 or matches[0][1].decode('ascii') != original[mission]:
            raise ValueError('original mission/BGM layout mismatch')
        found.add(mission)
        track = mapping[mission]
        if track not in original.values():
            raise ValueError('redirect track outside original PAL act catalog')
        edits.append((matches[0].start(1), matches[0].end(1), track.encode('ascii')))
    if found != set(mapping):
        raise ValueError('missing mission in original script')
    for start, end, value in reversed(edits):
        script = script[:start] + value + script[end:]
    return script


def patch_music(source, output, seed, mode):
    if mode not in ('per_world', 'anywhere') or not seed:
        raise ValueError('music patch requires seed and per_world/anywhere mode')
    if Path(str(output) + '.json').exists():
        raise ValueError('output manifest already exists')
    archive = CPK(source)
    banks = [row for row in archive.toc.rows if row['FileName'] == 'bgm.strm.csb']
    if len(banks) != 1:
        raise ValueError('PAL BGM cue bank not unique')
    bank = UTF(archive.read(banks[0]))
    cue = next(row for row in bank.rows if row['name'] == 'CUE')
    offset, size = cue['utf']
    cues = UTF(bank.data[bank.binary + offset:bank.binary + offset + size])
    # Lua BGM values are cue aliases, not necessarily AAX basenames. For
    # example Act 4 reuses a waveform through its own named cue.
    available = {row['name'] for row in cues.rows}
    mapping = plan_music(seed, mode, available)
    indices = [index for index, row in enumerate(archive.toc.rows)
               if row['DirName'] == '' and row['FileName'] == 'actstgmission.lua']
    if len(indices) != 1:
        raise ValueError('original mission script not unique')
    index = indices[0]
    original = archive.read(archive.toc.rows[index])
    replacement = replace_music(original, mapping)
    archive.replace_member(output, index, replacement, PAL_CPK_SHA256)
    manifest = {'seed': seed, 'mode': mode, 'source_cpk_sha256': PAL_CPK_SHA256,
                'original_script_sha256': hashlib.sha256(original).hexdigest(),
                'patched_script_sha256': hashlib.sha256(replacement).hexdigest(),
                'music_mapping': mapping,
                'validation': 'CPK decompression, PAL asset names, redirects and archive readback; audible playback unverified'}
    Path(str(output) + '.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--seed', required=True)
    parser.add_argument('--mode', required=True, choices=('per_world', 'anywhere'))
    args = parser.parse_args()
    result = patch_music(args.source, args.output, args.seed, args.mode)
    print(json.dumps({'output': str(args.output), 'manifest': str(args.output) + '.json',
                      'validation': result['validation']}, indent=2))


if __name__ == '__main__':
    main()
