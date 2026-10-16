"""Inspect private PAL finite donors without exporting or changing audio."""
import argparse
import hashlib
import json
from pathlib import Path
from ..client.cpk import CPK,UTF
from ..client.music_bank import CATALOG,GRAPHS
from ..client.asset_patch import PAL_CPK_SHA256


def audit(source):
    source=Path(source)
    with source.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=PAL_CPK_SHA256:
            raise ValueError('Original PAL CPK hash mismatch')
    archive=CPK(source)
    bank=archive.read(next(r for r in archive.toc.rows if r['FileName']=='bgm.strm.csb'))
    if hashlib.sha256(bank).hexdigest()!=CATALOG['bank_sha256']:
        raise ValueError('Original PAL bank hash mismatch')
    outer=UTF(bank)
    off,size=next(r['utf'] for r in outer.rows if r['name']=='SOUND_ELEMENT')
    sound=UTF(bank[outer.binary+off:outer.binary+off+size])
    result={}
    for cue in ('bgm_sys_op','bgm_sys_end'):
        audio=GRAPHS['graphs'][cue][0]['audio']
        metadata=next(r for r in sound.rows if r['name']==audio)
        row=next(r for r in archive.toc.rows if r['DirName']=='sound/Synth' and r['FileName']==audio.split('/')[-1])
        raw=archive.read(row);table=UTF(raw)
        result[cue]={'audio_sha256':hashlib.sha256(raw).hexdigest(),
            'sample_count':metadata['nsmpl'],'sample_rate':metadata['sfreq'],
            'duration_seconds':metadata['nsmpl']/metadata['sfreq'],
            'loop_flags':[r['lpflg'] for r in table.rows],
            'loop_cells':[list(c['lpflg']) for c in table.cells],
            'release_loop_enabled':False}
    return {'original_cpk_sha256':PAL_CPK_SHA256,'donors':result,
            'writes_performed':False,'audible_verified':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    args=parser.parse_args()
    print(json.dumps(audit(args.source),indent=2))
