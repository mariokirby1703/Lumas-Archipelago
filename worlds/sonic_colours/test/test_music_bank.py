"""Original PAL CSB/CPK verification, not an audible Dolphin test."""
import hashlib,json
from pathlib import Path
import pytest
from ..client.cpk import CPK,UTF
from ..client import music_bank
from ..client.runtime import Runtime
from ..client.journal import Journal
from ..client.hooks import NativeHooks
from ..client.state import SaveGuard
from .test_runtime import IDENTITY
from .test_native_assets import SOURCE
from . import generate


def bank():
    a=CPK(SOURCE)
    return a.read(next(r for r in a.toc.rows if r['FileName']=='bgm.strm.csb'))


@pytest.mark.parametrize('seed',range(100))
@pytest.mark.parametrize('mode',('per_world','anywhere'))
def test_seed_music_bank_permutations_preserve_compatibility_and_protected_cues(seed,mode):
    m=music_bank.plan(str(seed),mode)
    assert m==music_bank.plan(str(seed),mode)
    assert set(m)==set(m.values())==set(music_bank.CUES)
    assert all(m[n]==n for n in music_bank.PROTECTED)
    assert all(music_bank.CUES[n]['compatibility']==music_bank.CUES[d]['compatibility'] for n,d in m.items())
    if mode=='per_world': assert all(music_bank.group(n)==music_bank.group(d) for n,d in m.items())
    assert any(n!=d for n,d in m.items() if n not in music_bank.PROTECTED)


@pytest.mark.skipif(not SOURCE.exists(),reason='original PAL CPK absent')
@pytest.mark.parametrize('mode',('per_world','anywhere'))
def test_original_bgm_rewrite_changes_only_cue_synth_references(mode):
    original=bank();m=music_bank.plan('native-music-regression',mode)
    patched=music_bank.rewrite_bank(original,m)
    music_bank.validate_resource_bank(patched,m)
    assert len(patched)==len(original) and patched!=original
    b=UTF(original);o,n=next(r['utf'] for r in b.rows if r['name']=='CUE');base=b.binary+o
    cues=UTF(original[base:base+n]);allowed=set()
    decoded=UTF(patched[base:base+n])
    for i,row in enumerate(cues.rows):
        pos,fmt=cues.cells[i]['synth'];allowed.update(range(base+pos,base+pos+4))
        assert decoded.rows[i]=={**row,'synth':music_bank.CUES[m[row['name']]]['synth']}
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(original,patched)))
    assert m['bgm_sys_title']!='bgm_sys_title' or any(m[n]!=n for n in ('bgm_mlt_title','bgm_sys_result'))
    corrupted=bytearray(patched);corrupted[-1]^=1
    with pytest.raises(ValueError):music_bank.validate_resource_bank(bytes(corrupted),m)
    bad=m.copy();bad['bgm_sys_title']='bgm_jingle_drown'
    with pytest.raises(ValueError,match='incompatible or protected'):music_bank.rewrite_bank(original,bad)


@pytest.mark.skipif(not SOURCE.exists(),reason='original PAL CPK absent')
def test_actual_cpk_copy_and_seed_resource_selection(tmp_path):
    world=generate({'music_randomization':True}).worlds[1]
    slot=world.fill_slot_data();out=tmp_path/'music.cpk'
    before=SOURCE.stat().st_size
    manifest=music_bank.patch(SOURCE,out,slot['seed_name'],'anywhere')
    assert SOURCE.stat().st_size==before and out.exists()
    assert manifest['audible_verified'] is False
    path=Path(str(out)+'.json')
    selected=music_bank.load_manifest(path,slot)
    assert selected['resource_verified'] and not selected['audible_verified']
    with pytest.raises(ValueError,match='authenticated seed'):
        music_bank.load_manifest(path,{**slot,'seed_name':'another-seed'})
    with Journal(tmp_path/'journal',IDENTITY) as j:
        r=Runtime(slot,j,SaveGuard(j),NativeHooks())
        r.select_resource_music(path);assert r.resource_music['resource_verified']
        manifest['seed']='another-seed';path.write_text(json.dumps(manifest))
        r.select_resource_music(path);assert not r.resource_music['resource_verified']
        assert 'rejected' in r.music_status['status'].lower()
    with pytest.raises(ValueError):music_bank.patch(SOURCE,out,'other','anywhere')


def test_gui_client_command_preserves_windows_manifest_paths_with_spaces():
    from types import SimpleNamespace
    from ..client.client import SonicCommands
    selected = []
    runtime = SimpleNamespace(music_status={'audible_verified': False}, select_resource_music=selected.append)
    ctx = SimpleNamespace(runtime=runtime, music_resource_manifest=None)
    command = SonicCommands(ctx)
    path = r'C:\My Sonic Seed\music.cpk.json'
    command('/sonicmusic "'+path+'"')
    assert selected == [path] and ctx.music_resource_manifest == path
    command('/sonicmusic')
    assert selected == [path]
