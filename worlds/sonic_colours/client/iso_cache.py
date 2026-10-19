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


def _entry(root, source_hash):
    if (not isinstance(source_hash,str) or len(source_hash)!=64
            or any(c not in '0123456789abcdef' for c in source_hash)):
        raise ValueError('Invalid original cache source hash')
    return Path(root)/source_hash


def _retire_invalid(entry, observed):
    """Remove only the failed disposable entry, not a concurrent replacement."""
    if observed is None:return
    try:
        current=entry.lstat()
    except FileNotFoundError:return
    fields=('st_dev','st_ino','st_mtime_ns','st_ctime_ns')
    if any(getattr(current,f)!=getattr(observed,f) for f in fields):return
    root=entry.parent.resolve()
    if entry.is_symlink():
        entry.unlink()  # unlink the cache link, never its target
        return
    if entry.resolve().parent != root:
        raise ValueError('Unsafe invalid cache path')
    # First remove the entry from the publication name. A cancelled/failed
    # future store cannot leave this known-bad entry blocking every build.
    with tempfile.TemporaryDirectory(prefix='.invalid-',dir=root) as directory:
        quarantine=Path(directory).resolve()
        if quarantine.parent != root:raise ValueError('Unsafe cache quarantine')
        try:os.rename(entry,quarantine/'entry')
        except FileNotFoundError:return


def store(root, extracted, source_hash, cancel=None):
    """Atomically publish a complete immutable original tree, once per source."""
    root=Path(root);entry=_entry(root,source_hash)
    root.mkdir(parents=True,exist_ok=True)
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
    entry=_entry(root,source_hash);extracted=Path(extracted)
    if extracted.exists():raise FileExistsError('Cache work directory must be new')
    try:observed=entry.lstat()
    except FileNotFoundError:observed=None
    try:
        if entry.is_symlink() or (entry/'tree').is_symlink():raise ValueError('Symlink in partition cache')
        try:raw=(entry/'manifest.json').read_text(encoding='utf-8')
        except FileNotFoundError as error:raise ValueError('Partition cache manifest missing') from error
        record=json.loads(raw)
        if not isinstance(record,dict):raise ValueError('Invalid partition cache manifest')
        if record.get('version')!=1 or record.get('source_sha256')!=source_hash:
            raise ValueError('Partition cache identity/version differs')
        rows=record['files']
        if not isinstance(rows,dict) or not rows:raise ValueError('Empty partition cache manifest')
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
        # root. Never delete any user-selected source/output.
        if extracted.exists():
            resolved=extracted.resolve()
            if resolved.parent!=extracted.parent.resolve():raise ValueError('Unsafe cache work directory')
            shutil.rmtree(resolved)
        if observed is not None:
            progress('Original cache unavailable/damaged; extracting the original ISO instead')
            # Destination I/O errors (e.g. a full work volume) do not prove
            # corruption. Only retire an entry with failed cache validation.
            if isinstance(error,(ValueError,KeyError,TypeError)):
                try:_retire_invalid(entry,observed)
                except (OSError,ValueError) as cleanup_error:
                    progress('Invalid original cache could not be retired: '+str(cleanup_error))
        return False
