import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import time

import pytest

from ..client import generated_iso as registry, iso_patch
from .. import patch as patch_module


@pytest.fixture
def setup(tmp_path, monkeypatch):
    native, resource = 'a'*64, 'b'*64
    monkeypatch.setattr(iso_patch, 'plan', lambda **kwargs: (None, None, bytes.fromhex(native)))
    monkeypatch.setattr(patch_module, 'resource_component_id', lambda: resource)
    header = bytearray(32)
    header[:6] = b'SNCP8P'
    header[24:28] = bytes.fromhex('5d1c9ea3')
    source = tmp_path/'original.iso'
    source.write_bytes(header+b'original image')
    patch = SimpleNamespace(path=str(tmp_path/'player.apsoniccolours'), game='Sonic Colours (Wii)',
        player=1, player_name='Luma', slot_data={'seed_name':'seed-one', 'options':{'music_randomization':False}},
        ring_colors=None, initial_items=[], server='')
    Path(patch.path).write_bytes(b'player patch')
    commands=[]
    def forbidden(*args, **kwargs):
        commands.append(args)
        raise AssertionError('A cache hit must never invoke WIT or build resources')
    monkeypatch.setattr(iso_patch, 'command', forbidden)
    monkeypatch.setattr(iso_patch, 'patch_dol', forbidden)
    return SimpleNamespace(patch=patch, source=source, header=bytes(header), native=native,
                           resource=resource, commands=commands, directory=tmp_path)


def receipt(s, path=None):
    path=path or s.directory/'player-ap-upgraded.iso'
    path.write_bytes(s.header+b'generated verified image')
    data=registry.seed_data(s.patch)
    record={**data, 'identity':hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest(),
        'source_iso_sha256':iso_patch.sha(s.source), 'output_iso_sha256':iso_patch.sha(path),
        'pipeline_version':1, 'native_component_sha256':s.native,
        'resource_component_sha256':s.resource,'disc_id':'SNCP8P'}
    Path(str(path)+'.sonic.json').write_text(json.dumps(record),encoding='utf-8')
    return path,record


@pytest.mark.parametrize('change',['same','rename','move','download','server','no_server','upgraded'])
def test_persistent_cache_hits_do_not_build_or_duplicate(setup,change,monkeypatch):
    s=setup;output,_=receipt(s)
    assert iso_patch.install(s.patch,source=s.source)==output
    if change in ('rename','move','download'):
        folder=s.directory/'other' if change=='move' else s.directory
        folder.mkdir(exist_ok=True)
        s.patch.path=str(folder/'renamed.apsoniccolours')
        Path(s.patch.path).write_bytes(b'identical download')
    if change=='server':s.patch.server='another.example:1234'
    if change=='no_server':s.patch.server=None
    hashes=[]
    def no_large_hash(path,*args,**kwargs):
        hashes.append(path)
        raise AssertionError('Unchanged verified files must use the metadata fast path')
    monkeypatch.setattr(iso_patch,'sha',no_large_hash)
    assert iso_patch.install(s.patch,source=s.source)==output.resolve()
    assert not s.commands and not hashes
    assert list(s.directory.glob('*.iso'))==[s.source,output] or set(s.directory.glob('*.iso'))=={s.source,output}


def test_receipt_migration_and_client_restart(setup):
    s=setup;output,_=receipt(s)
    assert not (registry.root()/'entries').exists()
    assert iso_patch.find_generated_iso(s.patch,s.source)==output
    entries=list((registry.root()/'entries').glob('*.json'))
    assert len(entries)==1
    saved=json.loads(entries[0].read_text())
    assert len(saved['build_identity'])==64
    assert saved['build']['native_component_sha256']==s.native
    assert saved['build']['resource_component_sha256']==s.resource
    assert saved['build']['pipeline_version']==1 and saved['build']['player']==1
    # No process-local state is required for a fresh launcher invocation.
    s.patch.path=str(s.directory/'new-place'/'download.apsoniccolours')
    assert iso_patch.find_generated_iso(s.patch,s.source)==output


@pytest.mark.parametrize('damage',['missing_receipt','malformed','list','bad_payload','missing_iso','modified','same_size'])
def test_missing_or_modified_files_are_not_reused(setup,damage):
    s=setup;output,_=receipt(s)
    assert iso_patch.find_generated_iso(s.patch,s.source)==output
    meta=Path(str(output)+'.sonic.json')
    if damage=='missing_receipt':meta.unlink()
    elif damage=='malformed':meta.write_text('{bad')
    elif damage=='list':meta.write_text('[]')
    elif damage=='bad_payload':meta.write_text('{"slot_data": null}')
    elif damage=='missing_iso':output.unlink()
    elif damage=='same_size':output.write_bytes(b'x'*output.stat().st_size)
    else:output.write_bytes(b'modified')
    assert iso_patch.find_generated_iso(s.patch,s.source) is None


@pytest.mark.parametrize('difference',['player','seed','slot_data','initial','colors','region','source','native','resources','pipeline'])
def test_seed_disc_and_build_isolation(setup,difference,monkeypatch):
    s=setup;output,record=receipt(s)
    assert iso_patch.find_generated_iso(s.patch,s.source)==output
    if difference=='player':s.patch.player=2
    elif difference=='seed':s.patch.slot_data['seed_name']='another-seed'
    elif difference=='slot_data':s.patch.slot_data['options']['movement_unlocks']=True
    elif difference=='initial':s.patch.initial_items=[123]
    elif difference=='colors':s.patch.ring_colors={'1':'red'}
    elif difference=='region':
        data=bytearray(s.source.read_bytes());data[:6]=b'SNCE8P';s.source.write_bytes(data)
    elif difference=='source':s.source.write_bytes(s.source.read_bytes()+b'changed')
    elif difference=='native':monkeypatch.setattr(iso_patch,'plan',lambda **kwargs:(None,None,bytes.fromhex('c'*64)))
    elif difference=='resources':monkeypatch.setattr(patch_module,'resource_component_id',lambda:'d'*64)
    elif difference=='pipeline':
        record['pipeline_version']=999
        Path(str(output)+'.sonic.json').write_text(json.dumps(record))
    assert iso_patch.find_generated_iso(s.patch,s.source) is None
    assert output.is_file()


def test_gui_cache_hit_never_opens_patcher(setup,monkeypatch):
    s=setup;output,_=receipt(s)
    import sys
    monkeypatch.setitem(sys.modules,'tkinter',None)
    assert iso_patch.install_with_progress(s.patch,source=s.source)==output
    assert not s.commands


def test_server_persistence_does_not_create_connected_patches(setup):
    from ..client.launch import patch_server_address
    s=setup;before=list(s.directory.iterdir())
    assert patch_server_address(s.patch,'host.example:1234',gui=False)=='host.example:1234'
    assert patch_server_address(s.patch,gui=False)=='host.example:1234'
    assert patch_server_address(s.patch,'other.example:5678',gui=False)=='other.example:5678'
    assert [p for p in s.directory.iterdir() if p.is_file()]==before
    assert not list(s.directory.glob('*_connected*'))


def test_concurrent_builds_publish_once_and_second_launch_reuses(setup,monkeypatch):
    s=setup
    builds=[]
    def simulated_build(patch,**kwargs):
        hit=iso_patch.find_generated_iso(patch,s.source)
        if hit:return hit
        builds.append(1)
        time.sleep(.1)
        path,_=receipt(s)
        return path
    monkeypatch.setattr(iso_patch,'_install',simulated_build)
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda _:iso_patch.install(s.patch,source=s.source),range(2)))
    assert len(builds)==1 and results[0]==results[1]
    assert not s.commands


def test_changed_metadata_rehashes_then_returns_to_fast_path(setup,monkeypatch):
    s=setup;output,_=receipt(s)
    assert iso_patch.find_generated_iso(s.patch,s.source)==output
    output.write_bytes(output.read_bytes())
    actual=iso_patch.sha;hashed=[]
    def hashing(path,*args,**kwargs):
        hashed.append(Path(path));return actual(path,*args,**kwargs)
    monkeypatch.setattr(iso_patch,'sha',hashing)
    assert iso_patch.find_generated_iso(s.patch,s.source)==output
    assert hashed==[output]
    hashed.clear()
    assert iso_patch.find_generated_iso(s.patch,s.source)==output
    assert not hashed


@pytest.mark.parametrize('component',['native','resources'])
def test_existing_component_upgrade_is_found_in_previous_output_directory(setup,monkeypatch,component):
    s=setup;old,_=receipt(s)
    assert iso_patch.find_generated_iso(s.patch,s.source)==old
    upgraded=s.directory/'player-ap-new-build.iso'
    _,record=receipt(s,upgraded)
    if component=='native':
        record['native_component_sha256']='c'*64
        monkeypatch.setattr(iso_patch,'plan',lambda **kwargs:(None,None,bytes.fromhex('c'*64)))
    else:
        record['resource_component_sha256']='d'*64
        monkeypatch.setattr(patch_module,'resource_component_id',lambda:'d'*64)
    Path(str(upgraded)+'.sonic.json').write_text(json.dumps(record))
    s.patch.path=str(s.directory/'moved'/'same-patch.apsoniccolours')
    assert iso_patch.install(s.patch,source=s.source)==upgraded
    assert old.is_file() and upgraded.is_file() and not s.commands


def test_pal_and_ntsc_images_coexist_and_do_not_cross_reuse(setup):
    s=setup;pal,_=receipt(s)
    assert iso_patch.find_generated_iso(s.patch,s.source)==pal
    pal_source=s.source
    s.source=s.directory/'ntsc-original.iso'
    s.source.write_bytes(b'SNCE8P'+s.header[6:]+b'ntsc original')
    ntsc,record=receipt(s,s.directory/'ntsc-ap-image.iso')
    record['disc_id']='SNCE8P'
    Path(str(ntsc)+'.sonic.json').write_text(json.dumps(record))
    assert iso_patch.find_generated_iso(s.patch,s.source)==ntsc
    assert iso_patch.find_generated_iso(s.patch,pal_source)==pal


def test_malformed_registry_can_be_repaired_from_receipt(setup):
    s=setup;output,_=receipt(s)
    assert iso_patch.find_generated_iso(s.patch,s.source)==output
    for path in (registry.root()/'entries').glob('*.json'):path.write_text('{bad')
    assert iso_patch.find_generated_iso(s.patch,s.source)==output


def test_unrelated_client_changes_do_not_invalidate_iso(setup,monkeypatch):
    from ..client import versions
    s=setup;output,_=receipt(s)
    assert iso_patch.find_generated_iso(s.patch,s.source)==output
    monkeypatch.setattr(versions,'VERSION',{'client_only_update':True})
    assert iso_patch.install(s.patch,source=s.source)==output
    assert not s.commands


def process_lock_worker(directory, queue):
    from ..client import generated_iso as g
    g.root=lambda:Path(directory)
    with g.lock('same-build'):
        marker=Path(directory)/'build-count'
        count=int(marker.read_text()) if marker.exists() else 0
        time.sleep(.1)
        marker.write_text(str(count+1))
        queue.put(count+1)


def test_registry_locks_are_shared_between_processes(tmp_path):
    import multiprocessing
    ctx=multiprocessing.get_context('spawn')
    queue=ctx.Queue()
    workers=[ctx.Process(target=process_lock_worker,args=(str(tmp_path/'process-registry'),queue)) for _ in range(2)]
    try:
        for worker in workers:worker.start()
        assert sorted(queue.get(timeout=45) for _ in workers)==[1,2]
        for worker in workers:
            worker.join(timeout=45)
            assert worker.exitcode==0
    finally:
        for worker in workers:
            if worker.is_alive():worker.terminate()
            worker.join(timeout=5)
        queue.close()
        queue.join_thread()
