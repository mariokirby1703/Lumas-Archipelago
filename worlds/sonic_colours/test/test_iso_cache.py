"""Original partition reuse without trusting metadata or linking work files."""
import hashlib
import json
from pathlib import Path
import sys
import threading

import pytest

from ..client.iso_cache import store,restore,copy_hash
from ..client.iso_patch import command,sha


def prepared(tmp_path):
    original=tmp_path/'original';(original/'DATA/files').mkdir(parents=True)
    (original/'DATA/files/resource').write_bytes(b'original data')
    cache=tmp_path/'cache';store(cache,original,'a'*64)
    return original,cache,cache/('a'*64)


def test_restore_checks_bytes_and_work_changes_cannot_change_cached_original(tmp_path):
    original,cache,entry=prepared(tmp_path)
    work=tmp_path/'work';messages=[]
    assert restore(cache,work,'a'*64,messages.append)
    file=work/'DATA/files/resource';assert file.read_bytes()==b'original data'
    file.write_bytes(b'patched')
    assert (entry/'tree/DATA/files/resource').read_bytes()==b'original data'
    assert (original/'DATA/files/resource').read_bytes()==b'original data'
    assert messages


@pytest.mark.parametrize('damage',['bytes','size','missing','extra','manifest','traversal',
                                   'version','identity','empty','non_object','missing_manifest'])
def test_corrupt_cache_falls_back_without_leaving_partial_work(tmp_path,damage):
    original,cache,entry=prepared(tmp_path)
    file=entry/'tree/DATA/files/resource'
    if damage=='bytes':file.write_bytes(b'corrupted dat')
    elif damage=='size':file.write_bytes(b'x')
    elif damage=='missing':file.unlink()
    elif damage=='extra':(entry/'tree/extra').write_bytes(b'extra')
    elif damage=='manifest':(entry/'manifest.json').write_text('{bad')
    elif damage=='missing_manifest':(entry/'manifest.json').unlink()
    elif damage=='non_object':(entry/'manifest.json').write_text('[]')
    else:
        manifest=json.loads((entry/'manifest.json').read_text())
        if damage=='version':manifest['version']=0
        elif damage=='identity':manifest['source_sha256']='b'*64
        elif damage=='empty':manifest['files']={}
        else:manifest['files']['../escape']={'size':1,'sha256':'0'*64}
        (entry/'manifest.json').write_text(json.dumps(manifest))
    work=tmp_path/'work'
    assert not restore(cache,work,'a'*64,lambda _:None)
    assert not work.exists() and not (tmp_path/'escape').exists()
    assert not entry.exists()
    # The installer's successful extraction can now repopulate the same key;
    # the next build must use that repaired entry instead of extracting again.
    store(cache,original,'a'*64)
    assert restore(cache,work,'a'*64,lambda _:None)
    assert (work/'DATA/files/resource').read_bytes()==b'original data'
    assert not list(cache.glob('.invalid-*'))


def test_restore_does_not_remove_existing_work_directory(tmp_path):
    _,cache,_=prepared(tmp_path);work=tmp_path/'work';work.mkdir()
    (work/'keep').write_bytes(b'user')
    with pytest.raises(FileExistsError):restore(cache,work,'a'*64,lambda _:None)
    assert (work/'keep').read_bytes()==b'user'


def test_destination_io_error_preserves_valid_cache(tmp_path,monkeypatch):
    from ..client import iso_cache
    _,cache,entry=prepared(tmp_path)
    real=iso_cache.copy_hash
    def disk_full(*args):raise OSError('destination full')
    monkeypatch.setattr(iso_cache,'copy_hash',disk_full)
    assert not restore(cache,tmp_path/'failed','a'*64,lambda _:None)
    assert entry.is_dir()
    monkeypatch.setattr(iso_cache,'copy_hash',real)
    assert restore(cache,tmp_path/'next','a'*64,lambda _:None)


@pytest.mark.parametrize('key',['../outside','', 'A'*64, 'a'*63])
def test_cache_key_cannot_escape_root(tmp_path,key):
    original=tmp_path/'original';original.mkdir()
    with pytest.raises(ValueError,match='source hash'):store(tmp_path/'cache',original,key)
    with pytest.raises(ValueError,match='source hash'):restore(tmp_path/'cache',tmp_path/'work',key,lambda _:None)


def test_retirement_preserves_already_replaced_entry(tmp_path):
    from ..client.iso_cache import _retire_invalid
    original,cache,entry=prepared(tmp_path)
    observed=entry.lstat()
    entry.rename(cache/'old')
    store(cache,original,'a'*64)
    _retire_invalid(entry,observed)
    assert restore(cache,tmp_path/'work','a'*64,lambda _:None)


def test_cancelled_store_cannot_publish_partial_cache(tmp_path):
    original=tmp_path/'original';original.mkdir();(original/'a').write_bytes(b'data')
    cancel=threading.Event();cancel.set()
    with pytest.raises(InterruptedError):store(tmp_path/'cache',original,'b'*64,cancel)
    assert not (tmp_path/'cache'/('b'*64)).exists()


def test_hash_and_copy_support_cancel_without_touching_source(tmp_path):
    source=tmp_path/'source';source.write_bytes(b'test')
    assert copy_hash(source,tmp_path/'copy')==sha(source)==hashlib.sha256(b'test').hexdigest()
    cancel=threading.Event();cancel.set()
    with pytest.raises(InterruptedError):sha(source,cancel=cancel)
    assert source.read_bytes()==b'test'


def test_tool_output_streams_to_progress_and_retains_failure_tail(tmp_path):
    script=tmp_path/'tool.py';script.write_text('print("tool progress", flush=True)\nraise SystemExit(3)')
    messages=[]
    with pytest.raises(RuntimeError,match='tool progress'):
        command(sys.executable,[script],messages.append)
    assert any('tool progress' in row for row in messages)


def test_tool_cancellation_terminates_process(tmp_path):
    script=tmp_path/'tool.py';script.write_text('import time\nprint("ready",flush=True)\ntime.sleep(30)')
    cancel=threading.Event()
    def progress(_):cancel.set()
    with pytest.raises(InterruptedError):command(sys.executable,[script],progress,cancel)


@pytest.mark.parametrize('damage',[False,True])
def test_installer_warm_build_skips_source_verify_and_extraction_but_verifies_output(tmp_path,monkeypatch,damage):
    from types import SimpleNamespace
    from ..client import iso_patch
    from ..tools import build_hud_overlay
    header=bytearray(32);header[:6]=b'SNCP8P';header[24:28]=bytes.fromhex('5d1c9ea3')
    source=tmp_path/'original.iso';source.write_bytes(header)
    patch=SimpleNamespace(path=str(tmp_path/'seed.apsoniccolours'),game='Sonic Colours (Wii)',
                          player=1,player_name='Test',slot_data={'seed_name':'test','options':{'music_randomization':False}})
    monkeypatch.setattr(iso_patch,'PAL_DOL_SHA256',hashlib.sha256(b'dol').hexdigest())
    monkeypatch.setattr(iso_patch,'PAL_CPK_SHA256',hashlib.sha256(b'cpk').hexdigest())
    monkeypatch.setattr(iso_patch,'get_wit',lambda *a:Path('fake'))
    monkeypatch.setattr(iso_patch,'patch_dol',lambda raw,seed:(raw+b' patched',{}))
    monkeypatch.setattr(build_hud_overlay,'build',lambda source,output,**kw:Path(output).write_bytes(Path(source).read_bytes()+b' HUD'))
    calls=[]
    def tool(wit,args,progress,cancel):
        calls.append((args[0],args[1] if len(args)>1 else None))
        if args[0]=='EXTRACT':
            tree=Path(args[2])/'DATA';(tree/'sys').mkdir(parents=True);(tree/'files').mkdir()
            (tree/'sys/main.dol').write_bytes(b'dol');(tree/'sys/boot.bin').write_bytes(header)
            (tree/'files/sonic2010_0.cpk').write_bytes(b'cpk')
        if args[0]=='COPY':Path(args[2]).write_bytes(header+b'output')
    monkeypatch.setattr(iso_patch,'command',tool)
    cache=tmp_path/'cache'
    for name in ('cold','warm','repaired'):
        if damage and name=='warm':
            (cache/sha(source)/'manifest.json').write_text('{bad')
        cached=name!='cold' and not (damage and name=='warm')
        calls.clear();target=tmp_path/(name+'.iso')
        iso_patch.install(patch,source,target,cache_dir=cache)
        assert sum(verb=='EXTRACT' for verb,_ in calls)==(not cached)
        assert (('VERIFY',source) in calls)==(not cached)
        assert sum(verb=='VERIFY' for verb,_ in calls)==(1 if cached else 2)
        record=json.loads(Path(str(target)+'.sonic.json').read_text())
        assert record['original_cache_used']==cached
    assert (tmp_path/'cold.iso').read_bytes()==(tmp_path/'warm.iso').read_bytes()
    assert source.read_bytes()==header
