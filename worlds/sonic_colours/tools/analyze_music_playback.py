"""Extract all PAL BGM loop/control evidence; never modifies game resources."""
import hashlib
import json
import os
from pathlib import Path
import sys
os.environ.setdefault('AP_TEST_WORLDS', 'sonic_colours')
os.environ.setdefault('SKIP_REQUIREMENTS_UPDATE', '1')
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from worlds.sonic_colours.client.cpk import CPK, UTF
from worlds.sonic_colours.world_constants import load_data


def analyze(root):
    catalog = load_data('bgm_cues.json'); graphs = load_data('bgm_graphs.json')
    archive = CPK(root / 'notes/memdumps_and_more/sonic2010_0.cpk')
    raw = archive.read(next(r for r in archive.toc.rows if r['FileName'] == 'bgm.strm.csb'))
    assert hashlib.sha256(raw).hexdigest() == catalog['bank_sha256']
    outer = UTF(raw)
    tables = {r['name']: UTF(raw[outer.binary+r['utf'][0]:outer.binary+sum(r['utf'])]) for r in outer.rows}
    synth = {r['synname']: r for r in tables['SYNTH'].rows}
    sounds = {r['name']: r for r in tables['SOUND_ELEMENT'].rows}
    audio = {}
    for row in sounds.values():
        aax = archive.read(next(r for r in archive.toc.rows if r['DirName'] == 'sound/Synth'
                                and r['FileName'] == row['name'].split('/')[-1]))
        segments = UTF(aax).rows
        audio[row['name']] = {'loop_segments': [s['lpflg'] for s in segments],
                             'aax_sha256': hashlib.sha256(aax).hexdigest(),
                             **{k: row[k] for k in ('fmt','nch','stmflg','sfreq','nsmpl')}}
    cues = {}
    for cue in catalog['cues']:
        name = cue['name']; root_node = synth[cue['synth']]
        leaves = graphs['graphs'][name]
        cues[name] = {'cue_flags':cue['flags'], 'root_type':root_node['syntype'],
                      'native_repeat':root_node['repeat'], 'leaf_audio':[l['audio'] for l in leaves],
                      'audio_has_loop':any(1 in audio[l['audio']]['loop_segments'] for l in leaves)}
    return {'bank_sha256':catalog['bank_sha256'], 'cues':cues, 'audio':audio}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    result = analyze(root)
    (root / 'data/bgm_playback.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Verified',len(result['cues']),'cues;',sum(not r['audio_has_loop'] for r in result['cues'].values()),'finite audio donors')
