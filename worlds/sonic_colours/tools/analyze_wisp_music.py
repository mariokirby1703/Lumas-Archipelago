"""Reproduce PAL Wisp cue/graph evidence from the user's original ELF/CPK.

Run from the repository root. Writes metadata only, never patches game assets.
"""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

os.environ.setdefault('AP_TEST_WORLDS', 'sonic_colours')
os.environ.setdefault('SKIP_REQUIREMENTS_UPDATE', '1')
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from worlds.sonic_colours.client.cpk import CPK, UTF
from worlds.sonic_colours.client.music_bank import CATALOG, CUES
from worlds.sonic_colours.tools.ppc import Executable
from worlds.sonic_colours.world_constants import NATIVE_COLOURS


def analyze(root):
    e = Executable(root / 'notes/Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf')
    archive = CPK(root / 'notes/memdumps_and_more/sonic2010_0.cpk')
    raw = archive.read(next(r for r in archive.toc.rows if r['FileName'] == 'bgm.strm.csb'))
    assert hashlib.sha256(raw).hexdigest() == CATALOG['bank_sha256']
    def name_at(pointer):
        return e.read(pointer, 64).split(b'\0')[0].decode()
    rows = {}
    for index, colour in enumerate(NATIVE_COLOURS):
        cell = 0x80771970 + index * 4
        pointer, = struct.unpack('>I', e.read(cell, 4))
        rows[name_at(pointer)] = {'transformation': colour, 'native_colour': index,
                                  'selector_cell': f'0x{cell:08X}', 'selection': 'actor+EC native colour'}
    for cell, title, condition in (
        (0x808F1F78, 'Yellow Drill (underwater)', 'native colour 0 and actor+DD nonzero'),
        (0x808F1F80, 'Multi-Wisp common', 'actor+64 mode 2, actor+F0 variant 0'),
        (0x808F1F84, 'Multi-Wisp united', 'actor+64 mode 2, actor+F0 variant 1'),
    ):
        pointer, = struct.unpack('>I', e.read(cell, 4))
        rows[name_at(pointer)] = {'transformation': title, 'selector_cell': f'0x{cell:08X}',
                                  'selection': condition}
    assert set(rows) == {n for n in CUES if n.startswith('bgm_pha_')}
    pointer, = struct.unpack('>I', e.read(0x808F1F88, 4))
    assert name_at(pointer) == 'bgm_jingle_super_sonic'
    outer = UTF(raw)
    tables = {r['name']: UTF(raw[outer.binary+r['utf'][0]:outer.binary+sum(r['utf'])]) for r in outer.rows}
    synth = {r['synname']: r for r in tables['SYNTH'].rows}
    sounds = {r['name']: r for r in tables['SOUND_ELEMENT'].rows}
    for cue, row in rows.items():
        node = synth[CUES[cue]['synth']]
        assert node['syntype'] == 0 and node['cmplxtype'] == 0
        controls = [r for r in tables['ISAAC'].rows if r['ptname'].startswith(node['synname']+'/')]
        assert len(controls) == 1 and controls[0]['name'] == 'filter'
        sound = sounds[node['lnkname']]
        aax = archive.read(next(r for r in archive.toc.rows if r['DirName'] == 'sound/Synth'
                                and r['FileName'] == node['lnkname'].split('/')[-1]))
        loop = [r['lpflg'] for r in UTF(aax).rows]
        # Rocket is deliberately a finite one-shot in the original game.
        # Do not invent a repeat parameter for this older CRI implementation.
        assert 1 in loop or cue == 'bgm_pha_rkt' and loop == [0]
        row.update(cue_id=CUES[cue]['id'], cue_flags=CUES[cue]['flags'],
                   audio=node['lnkname'], volume=node['volume'], p3d_volume=node['p3d_vo'],
                   sound={k: sound[k] for k in ('fmt', 'nch', 'stmflg', 'sfreq', 'nsmpl')},
                   aax_loop_segments=loop, aax_sha256=hashlib.sha256(aax).hexdigest(),
                   filter_graph={'parameter': controls[0]['ptname'], 'type': controls[0]['type'],
                                 'bytes': controls[0]['grph'][1]})
    return {'bank_sha256': CATALOG['bank_sha256'], 'native_selector': '0x801F8DB0',
            'native_selector_sha256': hashlib.sha256(e.read(0x801F8DB0, 0x184)).hexdigest(),
            'protected_override': 'bgm_jingle_super_sonic', 'cues': dict(sorted(rows.items()))}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    result = analyze(root)
    (root / 'data/bgm_transformations.json').write_text(json.dumps(result, indent=2)+'\n')
    print(f"Verified {len(result['cues'])} transformation cues from original PAL data")
