import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from types import SimpleNamespace

import pytest

from ..client.regions import DISC_IDS,supported_header
from ..client import iso_patch
from ..client.memory import SonicMemory,MemoryUnavailable
from ..client.native_dol import Dol,patch_dol,PAL_DOL_SHA256
from ..patch import load_patch,InvalidDataError
from .test_seed_patch import make_patch


def header(disc,revision=0):
    data=bytearray(32);data[:6]=disc.encode();data[7]=revision
    data[24:28]=bytes.fromhex('5d1c9ea3')
    return bytes(data)


@pytest.mark.parametrize('disc',DISC_IDS)
def test_supported_iso_headers_and_saved_path(tmp_path,disc):
    path=tmp_path/'original.iso';path.write_bytes(header(disc))
    assert iso_patch.disc_header(path)==header(disc)
    assert supported_header(header(disc))
    path.write_bytes(header(disc,1))
    with pytest.raises(ValueError):iso_patch.disc_header(path)


@pytest.mark.parametrize('disc',['SNCJ8P','SMNE01','SNCE00'])
def test_other_regions_and_games_remain_rejected(tmp_path,disc):
    path=tmp_path/'original.iso';path.write_bytes(header(disc))
    with pytest.raises(ValueError):iso_patch.disc_header(path)


def test_client_rejects_unknown_ntsc_revision_before_native_reads():
    from ..client.versions import verify_revision
    memory=SimpleNamespace(error=MemoryUnavailable,
        read_bytes=lambda address,size:header('SNCE8P',1)[:size],read_u8=lambda address:1)
    with pytest.raises(MemoryUnavailable,match='unknown_revision'):verify_revision(memory)
    assert memory.revision_observation['verified'] is False


def test_patch_container_supports_both_regions_and_old_pal_metadata(tmp_path):
    path=tmp_path/'seed.apsoniccolours';make_patch(path)
    with zipfile.ZipFile(path) as z:contents={name:z.read(name) for name in z.namelist()}
    manifest=json.loads(contents['archipelago.json'])
    assert manifest['supported_disc_ids']==list(DISC_IDS)
    manifest.pop('supported_disc_ids')
    contents['archipelago.json']=json.dumps(manifest).encode()
    with zipfile.ZipFile(path,'w') as z:
        for name,data in contents.items():z.writestr(name,data)
    assert load_patch(path).get_manifest()['supported_disc_ids']==list(DISC_IDS)
    manifest['supported_disc_ids']=['SNCJ8P']
    contents['archipelago.json']=json.dumps(manifest).encode()
    with zipfile.ZipFile(path,'w') as z:
        for name,data in contents.items():z.writestr(name,data)
    with pytest.raises(InvalidDataError):load_patch(path)


@pytest.mark.parametrize('disc',DISC_IDS)
def test_original_and_patched_executable_validation_in_both_regions(disc):
    path=Path('worlds/sonic_colours/notes/NTSC-U/main.dol')
    if not path.exists():pytest.skip('private verified shared PAL/NTSC-U main.dol absent')
    source=path.read_bytes()
    assert hashlib.sha256(source).hexdigest()==PAL_DOL_SHA256
    for data in (source,patch_dol(source,'RegionsTest')[0]):
        image=Dol(data)
        class Backend:
            def read_bytes(self,address,size):
                if address==0x80000000:return header(disc)[:size]
                if address==0x80000007:return bytes(size)
                try:return image.read(address,size)
                except ValueError:return bytes(size)
        memory=SonicMemory(Backend());memory.verify_revision()
        assert memory.revision_observation['disc_id']==disc
        image.data[image.offset(0x80004000,4)]^=1
        with pytest.raises(MemoryUnavailable):memory.verify_revision()


def test_ntsc_shared_mem2_requires_the_same_verified_mapping(monkeypatch):
    from .test_mem2_shared import setup
    from ..client.mem2_shared import WindowsSharedMEM2
    engine,kernel,data,shared,frame=setup(monkeypatch)
    data[0x80000000,8]=shared[0,8]=header('SNCE8P')[:8]
    alias=WindowsSharedMEM2(engine,writable=False)
    alias.validate_source()
    shared[0,8]=header('SNCP8P')[:8]
    with pytest.raises(RuntimeError):alias.validate_source()
    alias.close()


@pytest.mark.parametrize('disc,partition,output,error',[
    ('SNCP8P','SNCP8P','SNCP8P',None),
    ('SNCE8P','SNCE8P','SNCE8P',None),
    ('SNCE8P','SNCP8P','SNCE8P','DATA partition'),
    ('SNCE8P','SNCE8P','SNCP8P','Generated ISO'),
])
def test_wit_pipeline_preserves_region_and_original(monkeypatch,tmp_path,disc,partition,output,error):
    from ..tools import build_hud_overlay
    source=tmp_path/'original.iso';source.write_bytes(header(disc))
    patch=make_patch(tmp_path/'seed.apsoniccolours')
    target=tmp_path/'patched.iso'
    monkeypatch.setattr(iso_patch,'get_wit',lambda *args:tmp_path/'wit.exe')
    monkeypatch.setattr(shutil,'disk_usage',lambda *args:SimpleNamespace(free=100*1024**3))
    def command(wit,args,*rest):
        if args[0]=='EXTRACT':
            tree=Path(args[2])/'DATA';(tree/'sys').mkdir(parents=True);(tree/'files').mkdir()
            (tree/'sys/boot.bin').write_bytes(header(partition))
            (tree/'sys/main.dol').write_bytes(b'original executable')
            (tree/'files/sonic2010_0.cpk').write_bytes(b'original archive')
        if args[0]=='COPY':Path(args[2]).write_bytes(header(output))
    monkeypatch.setattr(iso_patch,'command',command)
    real_sha=iso_patch.sha
    def sha(path,*args):
        if Path(path).name=='main.dol':return iso_patch.PAL_DOL_SHA256
        if Path(path).name=='sonic2010_0.cpk':return iso_patch.PAL_CPK_SHA256
        return real_sha(path,*args)
    monkeypatch.setattr(iso_patch,'sha',sha)
    monkeypatch.setattr(iso_patch,'patch_dol',lambda data,*args,**kwargs:(data+b' patched',{}))
    monkeypatch.setattr(build_hud_overlay,'build',lambda source,target,**kwargs:Path(target).write_bytes(b'patched archive'))
    if error:
        with pytest.raises(ValueError,match=error):iso_patch.install(patch,source=source,target=target,cache_dir=False)
        assert not target.exists()
    else:
        assert iso_patch.install(patch,source=source,target=target,cache_dir=False)==target
        assert target.read_bytes()==header(disc)
        record=json.loads(Path(str(target)+'.sonic.json').read_text())
        assert record['disc_id']==disc
        assert record['live_verified'] is False and record['boot_verified'] is False
    assert source.read_bytes()==header(disc)
