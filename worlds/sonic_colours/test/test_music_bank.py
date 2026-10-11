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
@pytest.mark.parametrize('mode',('anywhere',))
def test_seed_music_bank_permutations_cover_all_87_cues(seed,mode):
    m=music_bank.plan(str(seed),mode)
    assert m==music_bank.plan(str(seed),mode)
    assert set(m)==set(m.values())==set(music_bank.CUES)
    assert len(m) == 87 and all(n != d for n, d in m.items())
    if mode=='anywhere':
        assert any(music_bank.CUES[n]['compatibility']!=music_bank.CUES[d]['compatibility'] for n,d in m.items())
    assert all(music_bank.AUDIO['cues'][n] != music_bank.AUDIO['cues'][d] for n,d in m.items())


@pytest.mark.skipif(not SOURCE.exists(),reason='original PAL CPK absent')
@pytest.mark.parametrize('mode',('anywhere',))
def test_original_bgm_rewrite_changes_only_audio_leaves_preserving_control_graphs(mode):
    original=bank();m=music_bank.plan('native-music-regression',mode)
    patched=music_bank.rewrite_bank(original,m)
    music_bank.validate_resource_bank(patched,m)
    assert len(patched)==len(original) and patched!=original
    b=UTF(original);o,n=next(r['utf'] for r in b.rows if r['name']=='CUE');base=b.binary+o
    cues=UTF(original[base:base+n]);allowed={pos for leaves in music_bank.GRAPHS['graphs'].values()
                                          for leaf in leaves for pos in range(leaf['cell'],leaf['cell']+4)}
    decoded=UTF(patched[base:base+n])
    for i,row in enumerate(cues.rows):
        assert decoded.rows[i]==row
    assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(original,patched)))
    assert m['bgm_sys_title']!='bgm_sys_title' or any(m[n]!=n for n in ('bgm_mlt_title','bgm_sys_result'))
    corrupted=bytearray(patched);corrupted[-1]^=1
    with pytest.raises(ValueError):music_bank.validate_resource_bank(bytes(corrupted),m)
    bad=m.copy();bad['bgm_sys_title']='bgm_jingle_drown'
    with pytest.raises(ValueError,match='permutation'):music_bank.rewrite_bank(original,bad)


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


def test_reported_aquarium_seed_changes_actual_audio_not_aliases():
    mapping = music_bank.plan('53608322755801233751', 'anywhere')
    for name in (*[f'bgm_stg5{i}0_qua' for i in range(1,7)], 'bgm_zmap_qua'):
        assert music_bank.AUDIO['cues'][name] != music_bank.AUDIO['cues'][mapping[name]]
    assert any(not mapping[name].startswith('bgm_stg5') for name in mapping if name.startswith('bgm_stg5'))


@pytest.mark.skipif(not SOURCE.exists(),reason='original PAL CPK absent')
def test_aquarium_act_three_world_map_audio_retains_filter_and_boost_graph():
    import struct
    from ..client.live_music import recover_original
    original=bank(); mapping=music_bank.plan('forced-cross-category','off')
    # Reciprocal swaps form a permutation and exercise both graph shapes.
    pairs=(('bgm_stg530_qua','bgm_zmap_rso'),('bgm_mlt_a','bgm_boss_Jellyboss'),
           ('bgm_sys_title','bgm_stg110_rso'))
    for a,b in pairs: mapping[a],mapping[b]=b,a
    patched=music_bank.rewrite_bank(original,mapping)
    for destination,donor in mapping.items():
        target=music_bank.GRAPHS['graphs'][destination]; source=music_bank.GRAPHS['graphs'][donor]
        assert [struct.unpack_from('>I',patched,x['cell'])[0] for x in target] == [source[min(k,len(source)-1)]['original_ref'] for k in range(len(target))]
    assert recover_original(patched)==original
    assert music_bank.rewrite_bank(recover_original(patched),music_bank.plan('off','off'))==original
    # Mixing normal and FX from different donors is not a valid adaptation.
    corrupt=bytearray(patched); leaves=music_bank.GRAPHS['graphs']['bgm_stg530_qua']
    struct.pack_into('>I',corrupt,leaves[1]['cell'],music_bank.GRAPHS['graphs']['bgm_zmap_qua'][0]['original_ref'])
    with pytest.raises(ValueError,match='mixed donor'):music_bank.recover_bank(bytes(corrupt))


@pytest.mark.skipif(not SOURCE.exists(),reason='original PAL CPK absent')
def test_legacy_compatible_bank_can_migrate_to_global_and_restore_vanilla():
    import struct
    from ..client.live_music import recover_original
    original=bank(); outer=UTF(original)
    offset,size=next(r['utf'] for r in outer.rows if r['name']=='CUE')
    base=outer.binary+offset;cue=UTF(original[base:base+size]);idx={r['name']:i for i,r in enumerate(cue.rows)}
    legacy=bytearray(original)
    for destination,donor in (('bgm_zmap_rso','bgm_zmap_qua'),('bgm_zmap_qua','bgm_zmap_rso')):
        assert music_bank.CUES[destination]['compatibility']==music_bank.CUES[donor]['compatibility']
        pos,_=cue.cells[idx[destination]]['synth'];source,_=cue.cells[idx[donor]]['synth']
        legacy[base+pos:base+pos+4]=original[base+source:base+source+4]
    recovered=recover_original(bytes(legacy));assert recovered==original
    updated=music_bank.rewrite_bank(recovered,music_bank.plan('global-migration','anywhere'))
    assert recover_original(updated)==original
