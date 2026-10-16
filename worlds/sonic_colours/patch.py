"""Official AP player patch containers; proprietary source files stay local."""
import hashlib
import json
from pathlib import Path
import zipfile
from importlib.resources import files
from functools import lru_cache
from worlds.Files import APAutoPatchInterface,AutoPatchRegister,InvalidDataError
from .world_constants import GAME
from .client.native_dol import ABI,PAL_DOL_SHA256,plan
from .client.asset_patch import PAL_CPK_SHA256

FORMAT=1
# This released component has the same seed/resource contract. Rebuilding
# from it installs the corrected wrapper traversal, never its old machine code.
UPGRADABLE_NATIVE_COMPONENTS={'0c27cd93a3589a8dad2a1a3debfb85495e4aa75ef61f0474352496bdac1976d3',
                             'ddbb9ab5e96a36deb330ba58d2773d093a032982a2b52809e9116b7126f30fd1',
                             '84207fd5a41582c96a49d1a89396be331f74aa0de2046725a389d119cf028fe4',
                             '6988a734ac3f5e8776d0a461d4f229967382886958c8cbe2412c267411eb8929',
                             '79fe3ce64a1bbce739ceaabc86486b72988b589aaeb1093318f5be277efc009d'}
UPGRADABLE_RESOURCES={'9281b474c4023c15944860247c65a4de6adc79a1282b8eb02862603dc91d9a20'}
# Same resource contract, with the Game Land overlay formerly behind the frame.
UPGRADABLE_RESOURCES.add('d8f49fe95368298932065e51d507bae00afdb50823fffd5ccf9b6efc01c20fd2')
UPGRADABLE_RESOURCES.add('c0b53f72da43de419d12151554433a5850cdadc851309fda11c3d9df37b9f0aa')
UPGRADABLE_NATIVE_COMPONENTS.update({'c3bfebc29447406ee3fad98473c140496c8a0870ed0c2101897b28e7bbc77ff4', 'f3155c39f82e1b8e8708f9ea1bfb993bb349d8d4bd40f6a8ffa5cf5a1d59fde4'})
UPGRADABLE_RESOURCES.update({'d6500135d5b7a36c618d00961974c223b5d5ef9dff8488751693330c11aa0a08', 'ab0276016b694b38761ecc47aab8c2506086d2c7e9dd5bebff8ba0a3dbeeb0e9', 'a72d8cd9d9f2226092a3ce4cee0944e97cde8585bb6c2f0c57e5566778739521'})

@lru_cache(maxsize=1)
def resource_component_id():
    root=files(__package__);digest=hashlib.sha256()
    for path in ('tools/build_hud_overlay.py','tools/hud_gncp.py','tools/hud_tpl.py',
                 'tools/hud_cpk.py','tools/hud_original_assets.py','tools/hud_preflight.py',
                 'client/music_bank.py','data/bgm_cues.json','data/bgm_graphs.json'):
        digest.update(path.encode());digest.update(root.joinpath(*path.split('/')).read_bytes())
    return digest.hexdigest()

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()

class SonicColoursPatch(APAutoPatchInterface):
    game=GAME
    patch_file_ending='.apsoniccolours'
    result_file_ending='.iso'
    procedure='custom'

    def __init__(self,*args,slot_data=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.slot_data=slot_data

    def get_manifest(self):
        manifest=super().get_manifest()
        if self.slot_data is None:raise ValueError('seed slot data missing')
        if type(self.player) is not int or self.player<1:raise ValueError('a positive AP player slot is required')
        seed=canonical({'game':GAME,'player':self.player,'player_name':self.player_name,'slot_data':self.slot_data})
        manifest.update(result_file_ending=self.result_file_ending,sonic_patch_format=FORMAT,native_abi=ABI,
                        seed_name=self.slot_data['seed_name'],disc_id='SNCP8P',revision=0,
                        source_hashes={'main.dol':PAL_DOL_SHA256,'sonic2010_0.cpk':PAL_CPK_SHA256},
                        components={'seed.json':hashlib.sha256(seed).hexdigest()},
                        native_component_sha256=plan()[2].hex(),resource_transform_version=1,
                        resource_component_sha256=resource_component_id())
        return manifest

    def write_contents(self,archive):
        manifest=self.get_manifest()
        files={'archipelago.json':canonical(manifest),
               'seed.json':canonical({'game':GAME,'player':self.player,'player_name':self.player_name,'slot_data':self.slot_data})}
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,10,14,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16;archive.writestr(info,data)

    def read_contents(self,archive):
        infos=archive.infolist();names=[i.filename for i in infos]
        if len(names)!=len(set(names)) or set(names)!={'archipelago.json','seed.json'}:raise InvalidDataError('invalid or duplicate patch components')
        if any(i.file_size>2*1024*1024 for i in infos):raise InvalidDataError('patch component too large')
        manifest=super().read_contents(archive)
        legacy=(manifest.get('native_abi') in (1,2) and manifest.get('native_component_sha256') in {plan()[2].hex(),*UPGRADABLE_NATIVE_COMPONENTS}
                and manifest.get('resource_component_sha256') in UPGRADABLE_RESOURCES)
        if (manifest.get('game')!=GAME or manifest.get('sonic_patch_format')!=FORMAT
                or not (manifest.get('native_abi')==ABI or legacy) or manifest.get('disc_id')!='SNCP8P' or manifest.get('revision')!=0
                or manifest.get('native_component_sha256') not in {plan()[2].hex(),*UPGRADABLE_NATIVE_COMPONENTS}
                or manifest.get('resource_transform_version')!=1
                or not (manifest.get('resource_component_sha256')==resource_component_id() or legacy)
                or manifest.get('source_hashes')!={'main.dol':PAL_DOL_SHA256,'sonic2010_0.cpk':PAL_CPK_SHA256}):
            raise InvalidDataError('unsupported Sonic Colours patch/ABI; use the generating APWorld version')
        raw=archive.read('seed.json')
        if manifest.get('components')!={'seed.json':hashlib.sha256(raw).hexdigest()}:raise InvalidDataError('seed component integrity failure')
        data=json.loads(raw)
        if data.get('game')!=GAME or data.get('player')!=self.player or data.get('player_name')!=self.player_name:
            raise InvalidDataError('patch player identity differs')
        from .client.runtime import validate_slot
        self.slot_data=validate_slot(data['slot_data'])
        if manifest.get('seed_name')!=self.slot_data['seed_name'] or type(self.player) is not int or self.player<1:
            raise InvalidDataError('patch seed/slot identity invalid')
        return manifest

    def patch(self,target):
        self.read()
        from .client.iso_patch import install
        install(self,target=target)

class LegacySonicPatch(SonicColoursPatch):
    game=GAME
    patch_file_ending='.apsonic'
    def read(self,file=None):
        path=Path(file or self.path)
        if zipfile.is_zipfile(path):raise InvalidDataError('legacy .apsonic must be JSON metadata; use .apsoniccolours for containers')
        if path.stat().st_size>2*1024*1024:raise InvalidDataError('legacy seed metadata too large')
        data=json.loads(path.read_text(encoding='utf-8'))
        from .client.runtime import validate_slot
        if data.get('game')!=GAME:raise InvalidDataError('wrong legacy patch game')
        self.slot_data=validate_slot(data['slot_data']);self.player_name=data['player_name']
        self.player=data.get('player') # legacy files did not carry a slot number
        self.server=data.get('server','')

def load_patch(path):
    path=Path(path)
    if path.suffix.lower()=='.apsonic':patch=LegacySonicPatch(str(path))
    elif path.suffix.lower()=='.apsoniccolours':patch=SonicColoursPatch(str(path))
    else:raise InvalidDataError('expected .apsoniccolours or legacy .apsonic')
    patch.read();return patch

def migrate_legacy(source,target,player):
    source=Path(source);target=Path(target)
    if source.suffix.lower()!='.apsonic' or target.suffix.lower()!='.apsoniccolours':
        raise ValueError('Migration requires .apsonic input and .apsoniccolours output')
    if type(player) is not int or player<1:raise ValueError('Specify the legacy seed AP player slot number')
    old=load_patch(source)
    patch=SonicColoursPatch(str(target),player,old.player_name,old.server,slot_data=old.slot_data)
    with target.open('xb') as f:patch.write(f)
    return target

# Keep game lookup on the production container, while recognizing legacy input.
AutoPatchRegister.patch_types[GAME]=SonicColoursPatch
