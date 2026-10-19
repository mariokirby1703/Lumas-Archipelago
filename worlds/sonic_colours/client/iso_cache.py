"""Private, disposable original-partition cache. Never included in a release.

Every restored byte is hashed while copying; timestamps are not integrity
proofs. Work files are separate copies, never writable links to the cache.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile


def check_cancel(cancel):
    if cancel and cancel.is_set():
        raise InterruptedError('ISO build cancelled')


def copy_hash(source, target, cancel=None):
    digest=hashlib.sha256()
    with Path(source).open('rb') as src, Path(target).open('xb') as dst:
        while chunk:=src.read(4*1024*1024):
            check_cancel(cancel)
            digest.update(chunk);dst.write(chunk)
    return digest.hexdigest()


def _files(root):
    for path in sorted(root.rglob('*')):
        if path.is_symlink():raise ValueError('Symlink in partition cache')
        if path.is_file():yield path.relative_to(root).as_posix(),path


def store(root, extracted, source_hash, cancel=None):
    """Atomically publish a complete immutable original tree, once per source."""
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    entry=root/source_hash
    if entry.exists():return
    with tempfile.TemporaryDirectory(prefix='.prepare-',dir=root) as directory:
        tmp=Path(directory);tree=tmp/'tree';tree.mkdir();rows={}
        for name,path in _files(Path(extracted)):
            check_cancel(cancel)
            dest=tree/name;dest.parent.mkdir(parents=True,exist_ok=True)
            rows[name]={'sha256':copy_hash(path,dest,cancel),'size':dest.stat().st_size}
        if not rows:raise ValueError('Empty original partition')
        (tmp/'manifest.json').write_text(json.dumps({'version':1,'source_sha256':source_hash,'files':rows}),encoding='utf-8')
        check_cancel(cancel)
        try:os.rename(tmp,entry)
        except FileExistsError:pass  # another installer published first


def restore(root, extracted, source_hash, progress, cancel=None):
    """Return False on a stale/damaged cache; caller re-extracts the original."""
    entry=Path(root)/source_hash;extracted=Path(extracted)
    if extracted.exists():raise FileExistsError('Cache work directory must be new')
    try:
        if entry.is_symlink() or (entry/'tree').is_symlink():raise ValueError('Symlink in partition cache')
        record=json.loads((entry/'manifest.json').read_text(encoding='utf-8'))
        if record.get('version')!=1 or record.get('source_sha256')!=source_hash:return False
        rows=record['files']
        if not isinstance(rows,dict) or not rows:return False
        # Validate all names before any destination creation.
        for name in rows:
            path=PurePosixPath(name)
            if (not name or '\\' in name or ':' in name or path.is_absolute()
                    or '..' in path.parts or path.as_posix()!=name):
                raise ValueError('Unsafe partition cache path')
        expected=set(rows)
        if {name for name,_ in _files(entry/'tree')}!=expected:
            raise ValueError('Partition cache file set differs')
        extracted.mkdir()
        total=sum(row['size'] for row in rows.values());done=0
        for name,row in rows.items():
            check_cancel(cancel)
            source=entry/'tree'/name;dest=extracted/name
            if source.stat().st_size!=row['size']:raise ValueError('Partition cache size differs')
            dest.parent.mkdir(parents=True,exist_ok=True)
            if copy_hash(source,dest,cancel)!=row['sha256']:raise ValueError('Partition cache hash differs')
            done+=row['size']
            progress(f'Checking/copying cached original partition: {done//1048576}/{total//1048576} MiB')
        return True
    except (OSError,ValueError,KeyError,TypeError) as error:
        if isinstance(error,InterruptedError):raise
        # This is a freshly created work directory inside the installer's temp
        # root. Never delete the cache or any user-selected source/output.
        if extracted.exists():
            resolved=extracted.resolve()
            if resolved.parent!=extracted.parent.resolve():raise ValueError('Unsafe cache work directory')
            shutil.rmtree(resolved)
        if entry.exists():progress('Original cache unavailable/damaged; extracting the original ISO instead')
        return False
