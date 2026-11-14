"""Read-only verification of the pinned native save's serialized character bank."""
from pathlib import Path
import hashlib
import os
import json
from delivery_marker import CHARACTER_SAVE_OFFSET,MODEL_COUNT,NATIVE_SAVE_SIZE,marker_from_save
from inventory_reader import pointer
from research_profile import ABILITY_NAMES


def steam_save_candidates():
    roots={Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Steam'}
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:
            roots.add(Path(winreg.QueryValueEx(key,'SteamPath')[0]))
    except (ImportError,OSError):pass
    return sorted({p for root in roots for p in root.glob('userdata/*/578330/remote/savedgames/slot*/game*.legocityundercoversavegamedata')})


def read_save(path):
    path=Path(path)
    before=path.stat()
    if before.st_size!=NATIVE_SAVE_SIZE:raise ValueError('Unsupported native save size')
    data=path.read_bytes();after=path.stat()
    if (before.st_mtime_ns,before.st_size)!=(after.st_mtime_ns,after.st_size):
        raise RuntimeError('Native save changed during verification')
    marker_from_save(data)  # Validate exact layout before using offsets.
    return data


def resolve_save(read,base,explicit=None):
    bank=pointer(read,base+0x1c7cbb8);state=read(bank,0x580)
    if explicit:
        path=Path(explicit).resolve();data=read_save(path)
        if data[CHARACTER_SAVE_OFFSET:CHARACTER_SAVE_OFFSET+0x580]!=state:
            raise RuntimeError('No unique matching native save: selected file differs from the loaded character bank')
        if read(bank,0x580)!=state:raise RuntimeError('Inventory changed during save identity resolution')
        return path
    matches=[]
    for path in steam_save_candidates():
        try:
            data=read_save(path)
            if data[CHARACTER_SAVE_OFFSET:CHARACTER_SAVE_OFFSET+0x580]==state:matches.append(path.resolve())
        except (OSError,ValueError,RuntimeError):continue
    if read(bank,0x580)!=state:raise RuntimeError('Inventory changed during save identity resolution')
    if len(matches)!=1:raise RuntimeError('No unique matching native save; use --native-save-file for the loaded slot')
    return matches[0]


def model_saved(data,model):
    marker_from_save(data)
    if type(model) is not int or not 0<=model<MODEL_COUNT:raise ValueError('Model outside supported table')
    return bool(data[CHARACTER_SAVE_OFFSET+0x80+model])


def cheat_saved(data,index):
    marker_from_save(data)
    if type(index) is not int or not 0<=index<40:raise ValueError('Cheat outside pinned table')
    # Binding code 0x811a93..0x811b3b: model bank=profile+0x122e0,
    # cheat ownership=profile+0xfa80. The serialized profile begins at 0x2038.
    offset=CHARACTER_SAVE_OFFSET-0x122e0+0xfa80
    return bool(int.from_bytes(data[offset:offset+8],'little')&(1<<index))


ABILITY_CHUNK=bytes.fromhex('3d4f6d43 12000000 33')


def ability_saved(data,name):
    marker_from_save(data)
    if name not in ABILITY_NAMES:raise ValueError('Unbound native ability')
    # 0x90d90 serializes type 51 plus two pairs of uint32. 0x907b0
    # builds the first uint64 from manager+D8 (existing), the second from
    # +10B (pending). The container signature occurs once in all examined saves.
    if data.count(ABILITY_CHUNK)!=1:raise ValueError('Ability save chunk is not unique')
    offset=data.find(ABILITY_CHUNK)+len(ABILITY_CHUNK)
    existing=int.from_bytes(data[offset:offset+8],'little')
    pending=int.from_bytes(data[offset+8:offset+16],'little')
    if existing>>51 or pending>>51:raise ValueError('Ability save chunk exceeds native table')
    return bool(existing&(1<<ABILITY_NAMES.index(name)))


def save_evidence(path,data):
    return dict(save_confirmed=True,native_file=str(path),sha256=hashlib.sha256(data).hexdigest())


def ensure_backup(path,destination):
    """Back up the bound slot once before any native mutations; never edit it."""
    path=Path(path).resolve();destination=Path(destination)
    manifest=destination/'backup_manifest.json'
    if manifest.is_file():
        previous=json.loads(manifest.read_text(encoding='utf-8'))
        if previous['source_file']!=str(path):raise ValueError('Backup belongs to another native save')
        for row in previous['files']:
            if Path(row['name']).name!=row['name']:raise ValueError('Invalid backup filename')
            if hashlib.sha256((destination/row['name']).read_bytes()).hexdigest()!=row['sha256']:
                raise RuntimeError('Existing native backup failed integrity verification')
        return destination
    destination.mkdir(parents=True,exist_ok=True)
    read_save(path)
    rows=[]
    for source in sorted(path.parent.glob('*.legocityundercoversavegamedata')):
        if not 0<source.stat().st_size<=NATIVE_SAVE_SIZE:raise ValueError('Unexpected native backup file size')
        first=source.read_bytes();second=source.read_bytes()
        if first!=second:raise RuntimeError('Native save changed during backup; retry after saving')
        target=destination/source.name;temporary=target.with_suffix(target.suffix+'.tmp')
        temporary.write_bytes(first);temporary.replace(target)
        rows.append(dict(name=source.name,size=len(first),sha256=hashlib.sha256(first).hexdigest()))
    if path.name not in {r['name'] for r in rows}:raise ValueError('Main native save missing from backup')
    temporary=manifest.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(source_file=str(path),files=rows),indent=2),encoding='utf-8')
    temporary.replace(manifest)
    return destination
