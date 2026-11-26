"""Persistent lookup of verified, separately generated game images."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

PIPELINE_VERSION = 1


def root():
    import Utils
    return Path(Utils.user_path('sonic_colours_cache', 'generated-v1'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def seed_data(patch):
    from .boot_permissions import VERSION
    data = dict(game=patch.game, player=patch.player, player_name=patch.player_name,
                slot_data=patch.slot_data, boot_permissions_version=VERSION,
                initial_items=getattr(patch, 'initial_items', []))
    if getattr(patch, 'ring_colors', None) is not None:
        data['ring_colors'] = patch.ring_colors
    return data


def seed_identity(data):
    data = {k: data[k] for k in ('game', 'player', 'player_name', 'slot_data',
            'boot_permissions_version', 'initial_items', 'ring_colors') if k in data}
    slot = dict(data.get('slot_data', {}))
    for key in ('server', 'server_address'):
        slot.pop(key, None)
    data['slot_data'] = slot
    return digest(data)


def metadata(path):
    stat = Path(path).stat()
    if not Path(path).is_file():
        raise ValueError('Not a regular file')
    return {key: getattr(stat, key) for key in
            ('st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_dev', 'st_ino')}


def read(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.publish-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextmanager
def lock(key):
    directory = root() / 'locks'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / (key + '.lock')).open('a+b') as stream:
        stream.seek(0)
        # Windows permits locking a byte beyond EOF. Do not read/write that
        # byte before owning it: another launch may already hold its lock.
        if os.name == 'nt':
            import msvcrt
            while True:
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(.1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def source_hash(source, hash_file):
    source = Path(source).resolve()
    path = root() / 'sources' / (digest(str(source)) + '.json')
    before = metadata(source)
    old = read(path)
    if old.get('metadata') == before and valid_hash(old.get('sha256')):
        return old['sha256']
    value = hash_file(source)
    if metadata(source) != before:
        raise ValueError('Original ISO changed during verification')
    write(path, dict(metadata=before, sha256=value))
    return value


def valid_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def register(path, record, source, source_digest):
    path = Path(path).resolve()
    receipt = Path(str(path) + '.sonic.json')
    build = {key: record.get(key) for key in ('game','player','player_name','slot_data',
        'initial_items','ring_colors','boot_permissions_version','pipeline_version',
        'native_component_sha256','resource_component_sha256','disc_id')}
    build['source_iso_sha256'] = source_digest
    build_id = digest({'seed':seed_identity(record), 'source_iso_sha256':source_digest,
        **{key:record.get(key) for key in ('disc_id','pipeline_version',
           'native_component_sha256','resource_component_sha256')}})
    entry = dict(version=1, path=str(path), seed=seed_identity(record), build=build,
                 build_identity=build_id,
                 source_path=str(Path(source).resolve()), source_sha256=source_digest,
                 output_sha256=record['output_iso_sha256'], output_metadata=metadata(path),
                 receipt_metadata=metadata(receipt), receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest())
    write(root() / 'entries' / (digest(str(path)) + '.json'), entry)


def find(patch, source, target, native, resources, hash_file, header, log):
    source = Path(source).resolve()
    source_header = header(source)
    source_digest = source_hash(source, hash_file)
    expected = seed_data(patch)
    wanted = seed_identity(expected)
    legacy = hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
    entries = list((root() / 'entries').glob('*.json'))
    known = {}
    directories = {Path(patch.path).resolve().parent, Path(target).resolve().parent}
    candidates = [Path(target).resolve()]
    for file in entries:
        entry = read(file)
        if not isinstance(entry.get('path'), str):
            continue
        path = Path(entry['path'])
        if not path.is_absolute():
            continue
        known[str(path)] = entry
        directories.add(path.parent)
        if entry.get('seed') == wanted:
            candidates.append(path)
    for directory in directories:
        try:
            candidates.extend(Path(str(p)[:-11]) for p in directory.glob('*.iso.sonic.json'))
        except OSError as error:
            log(f'ISO cache miss: cannot search output directory: {directory}: {error}')
    for path in dict.fromkeys(candidates):
        receipt = Path(str(path) + '.sonic.json')
        if not path.is_file():
            if receipt.exists():log(f'ISO cache miss: image missing: {path}')
            continue
        record = read(receipt)
        if not record:
            log(f'ISO cache miss: missing/malformed receipt: {path}')
            continue
        # Older receipts contain either the complete seed payload or its exact digest.
        try:
            same_seed = seed_identity(record) == wanted if 'slot_data' in record else record.get('identity') == legacy
        except (TypeError,ValueError):
            log(f'ISO cache miss: malformed seed data in receipt: {path}')
            continue
        if not same_seed:
            log(f'ISO cache miss: seed/player or relevant seed data differ: {path}')
            continue
        if record.get('source_iso_sha256') != source_digest or record.get('disc_id', source_header[:6].decode()) != source_header[:6].decode():
            log(f'ISO cache miss: original disc identity/region differs: {path}')
            continue
        if record.get('pipeline_version') != PIPELINE_VERSION or record.get('native_component_sha256') != native:
            log(f'ISO cache miss: native components/pipeline require update: {path}')
            continue
        if record.get('resource_component_sha256') not in resources:
            log(f'ISO cache miss: resource components require update: {path}')
            continue
        if not valid_hash(record.get('output_iso_sha256')):
            log(f'ISO cache miss: missing output checksum: {path}')
            continue
        try:
            before, receipt_stat = metadata(path), metadata(receipt)
            entry = known.get(str(path), {})
            fast = (entry.get('output_metadata') == before and entry.get('receipt_metadata') == receipt_stat
                    and entry.get('output_sha256') == record['output_iso_sha256']
                    and entry.get('receipt_sha256') == hashlib.sha256(receipt.read_bytes()).hexdigest())
            if not fast and hash_file(path) != record['output_iso_sha256']:
                log(f'ISO cache miss: output checksum differs: {path}')
                continue
            if metadata(path) != before or metadata(receipt) != receipt_stat:
                log(f'ISO cache miss: files changed during validation: {path}')
                continue
            register(path, record if 'slot_data' in record else {**expected, **record}, source, source_digest)
        except (OSError, ValueError) as error:
            log(f'ISO cache miss: validation failed: {path}: {error}')
            continue
        log(f'ISO cache hit ({"metadata verified" if fast else "content verified/migrated"}): {path}')
        return path.resolve()
    log('ISO cache miss: no compatible verified generated ISO found')
    return None


def server(patch, value=None):
    path = root() / 'servers' / (seed_identity(seed_data(patch)) + '.json')
    if value is not None:
        write(path, {'server': value})
    return read(path).get('server')
