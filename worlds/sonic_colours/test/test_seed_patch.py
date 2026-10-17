import hashlib
import json
from pathlib import Path
import zipfile
import pytest
from worlds.Files import AutoPatchRegister,InvalidDataError,is_ap_player_container
from ..patch import SonicColoursPatch,load_patch,migrate_legacy
from ..client.native_dol import Dol,patch_dol,plan,branch,SIGNATURE
from ..client.memory import SonicMemory,MemoryUnavailable
from ..client.iso_patch import disc_header,install
from . import generate

def make_patch(path):
    slot=generate().worlds[1].fill_slot_data()
    patch=SonicColoursPatch(str(path),1,'SonicPlayer',slot_data=slot);patch.write()
    return patch


def test_room_download_server_injection_preserves_valid_patch_and_player(tmp_path):
    original=tmp_path/'generated.apsoniccolours';make_patch(original)
    with zipfile.ZipFile(original) as archive:members={n:archive.read(n) for n in archive.namelist()}
    manifest=json.loads(members['archipelago.json']);manifest['server']='archipelago.gg:38283'
    members['archipelago.json']=json.dumps(manifest).encode()
    downloaded=tmp_path/'room.apsoniccolours'
    with zipfile.ZipFile(downloaded,'w') as archive:
        for name,data in members.items():archive.writestr(name,data)
    patch=load_patch(downloaded)
    assert patch.server=='archipelago.gg:38283' and patch.player_name=='SonicPlayer'


def test_known_boost_crash_patch_can_rebuild_with_corrected_code(tmp_path):
    from ..patch import UPGRADABLE_NATIVE_COMPONENTS
    path=tmp_path/'released.apsoniccolours';original=make_patch(path)
    with zipfile.ZipFile(path) as z:members={n:z.read(n) for n in z.namelist()}
    manifest=json.loads(members['archipelago.json'])
    manifest['native_component_sha256']=next(iter(UPGRADABLE_NATIVE_COMPONENTS))
    members['archipelago.json']=json.dumps(manifest).encode()
    with zipfile.ZipFile(path,'w') as z:
        for name,data in members.items():z.writestr(name,data)
    assert load_patch(path).slot_data==original.slot_data

def test_official_container_generation_determinism_and_registration(tmp_path):
    a=tmp_path/'one.apsoniccolours';b=tmp_path/'two.apsoniccolours'
    patch=make_patch(a);patch.write(str(b))
    assert a.read_bytes()==b.read_bytes()
    assert is_ap_player_container(patch.game,a.read_bytes(),1)
    assert AutoPatchRegister.get_handler(str(a)) is SonicColoursPatch
    from ..components import run_client
    from worlds.LauncherComponents import components
    component=next(c for c in components if c.func is run_client)
    assert component.file_identifier(str(a))
    assert component.file_identifier(str(tmp_path/'old.apsonic'))
    loaded=load_patch(a)
    assert loaded.slot_data==patch.slot_data and loaded.player==1
    with zipfile.ZipFile(a) as z:assert set(z.namelist())=={'archipelago.json','seed.json'}

@pytest.mark.parametrize('field,value', [('game','Wrong'),('native_abi',999),('revision',1),
    ('source_hashes',{}),('seed_name','wrong'),('native_component_sha256','0'*64)])
def test_patch_rejects_wrong_identity_and_component_versions(tmp_path,field,value):
    path=tmp_path/'test.apsoniccolours';make_patch(path)
    with zipfile.ZipFile(path) as z:contents={n:z.read(n) for n in z.namelist()}
    metadata=json.loads(contents['archipelago.json']);metadata[field]=value
    contents['archipelago.json']=json.dumps(metadata).encode()
    with zipfile.ZipFile(path,'w') as z:
        for n,b in contents.items():z.writestr(n,b)
    with pytest.raises(InvalidDataError):load_patch(path)

def test_duplicate_corrupt_and_tampered_components(tmp_path):
    path=tmp_path/'test.apsoniccolours';make_patch(path)
    with zipfile.ZipFile(path,'a') as z:
        with pytest.warns(UserWarning):z.writestr('seed.json',b'{}')
    with pytest.raises(InvalidDataError):load_patch(path)
    path.write_bytes(b'PK broken')
    with pytest.raises(zipfile.BadZipFile):load_patch(path)

def test_legacy_metadata_is_explicit_and_migratable(tmp_path):
    path=tmp_path/'legacy.apsonic';patch=make_patch(tmp_path/'new.apsoniccolours')
    path.write_text(json.dumps({'game':patch.game,'player_name':'Legacy','slot_data':patch.slot_data}))
    loaded=load_patch(path);assert loaded.player is None and loaded.slot_data==patch.slot_data
    migrated=tmp_path/'migrated.apsoniccolours'
    migrate_legacy(path,migrated,2)
    assert load_patch(migrated).player==2
    with pytest.raises(FileExistsError):migrate_legacy(path,migrated,2)
    with pytest.raises(ValueError,match='slot'):migrate_legacy(path,tmp_path/'other.apsoniccolours',None)
    path.write_bytes(Path(patch.path).read_bytes())
    with pytest.raises(InvalidDataError,match='legacy'):load_patch(path)

def test_input_header_rejection_and_never_overwrite_original(tmp_path):
    source=tmp_path/'original.iso';header=bytearray(32);header[:6]=b'SNCP8P';header[24:28]=bytes.fromhex('5d1c9ea3')
    source.write_bytes(header);assert disc_header(source)==header
    patch=make_patch(tmp_path/'seed.apsoniccolours')
    with pytest.raises(ValueError,match='never'):install(patch,source,source)
    assert source.read_bytes()==header
    header[7]=1;source.write_bytes(header)
    with pytest.raises(ValueError,match='Revision 0'):disc_header(source)

def test_atomic_output_refuses_existing_unverified_file(tmp_path):
    source=tmp_path/'original.iso';header=bytearray(32);header[:6]=b'SNCP8P';header[24:28]=bytes.fromhex('5d1c9ea3');source.write_bytes(header)
    target=tmp_path/'output.iso';target.write_bytes(b'user data')
    patch=make_patch(tmp_path/'seed.apsoniccolours')
    with pytest.raises(FileExistsError):install(patch,source,target)
    assert target.read_bytes()==b'user data' and source.read_bytes()==header

def original_dol():
    path=Path(__file__).parents[1]/'notes/memdumps_and_more/main.dol'
    alternatives=[path,Path('C:/Users/Luma/Documents/Sonic Colors/DATA/sys/main.dol')]
    for p in alternatives:
        if p.exists():return p.read_bytes()
    pytest.skip('private original PAL DOL absent')

def test_native_migration_full_revision_handshake_and_returns():
    original=original_dol();patched,registry=patch_dol(original,'NativeTest')
    assert patched==patch_dol(original,'NativeTest')[0] and patched!=original
    image=Dol(patched)
    assert image.read(SIGNATURE,8)==b'SCAPNAT1'
    for hook in registry['hooks']:
        assert image.read(hook['hook'],4)==branch(hook['hook'],hook['target']).to_bytes(4,'big')
        assert image.read(hook['target']+hook['size']-4,4)==branch(hook['target']+hook['size']-4,hook['return']).to_bytes(4,'big')
    class Backend:
        def read_bytes(self,a,n):
            if a==0x80000000:return (b'SNCP8P'+bytes(2))[:n]
            if a==0x80000007:return bytes(1)
            try:return image.read(a,n)
            except ValueError:return bytes(n)
    memory=SonicMemory(Backend());memory.required_native_seed='NativeTest'
    assert memory.verify_revision()==hashlib.sha256(original).hexdigest()
    assert not memory.native_patch['gecko_required']
    memory.required_native_seed='wrong'
    with pytest.raises(MemoryUnavailable,match='another seed'):memory.verify_revision()
    memory.required_native_seed='NativeTest'
    address,old,new=plan()[0][0];image.replace(address,new,bytes(4))
    with pytest.raises(MemoryUnavailable,match='modified'):memory.verify_revision()

def test_dol_rejects_corrupt_original_and_out_of_range_branch():
    with pytest.raises(ValueError,match='SHA256'):patch_dol(bytes(256),'x')
    with pytest.raises(ValueError,match='range'):branch(0x80000000,0x90000000)

def test_verified_iso_cache_and_tamper_refusal(tmp_path):
    from ..patch import resource_component_id
    source=tmp_path/'original.iso';header=bytearray(32);header[:6]=b'SNCP8P';header[24:28]=bytes.fromhex('5d1c9ea3');source.write_bytes(header)
    target=tmp_path/'out.iso';target.write_bytes(b'verified generated image')
    patch=make_patch(tmp_path/'seed.apsoniccolours')
    seed_data={'game':patch.game,'player':patch.player,'player_name':patch.player_name,'slot_data':patch.slot_data}
    record={'identity':hashlib.sha256(json.dumps(seed_data,sort_keys=True).encode()).hexdigest(),
            'source_iso_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'native_component_sha256':plan()[2].hex(),'pipeline_version':1,
            'resource_component_sha256':resource_component_id(),
            'output_iso_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    Path(str(target)+'.sonic.json').write_text(json.dumps(record))
    assert install(patch,source,target)==target.resolve()
    target.write_bytes(b'tampered')
    with pytest.raises(FileExistsError):install(patch,source,target)

def test_insufficient_space_fails_before_tool_or_source_mutation(tmp_path,monkeypatch):
    from ..client import iso_patch
    source=tmp_path/'original.iso';header=bytearray(32);header[:6]=b'SNCP8P';header[24:28]=bytes.fromhex('5d1c9ea3');source.write_bytes(header)
    patch=make_patch(tmp_path/'seed.apsoniccolours')
    from types import SimpleNamespace
    monkeypatch.setattr(iso_patch.shutil,'disk_usage',lambda p:SimpleNamespace(free=0))
    with pytest.raises(OSError,match='space'):install(patch,source,tmp_path/'out.iso')
    assert source.read_bytes()==header and not (tmp_path/'out.iso').exists()
