"""Bounded file-hash cache. Process identity and mutation signatures are not cached."""
import hashlib
import os
import time

_cache={}


def file_digest(path,ttl=5.0):
    key=os.path.normcase(os.path.abspath(path))
    with open(path,'rb') as stream:
        before=os.fstat(stream.fileno())
        identity=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)
        cached=_cache.get(key)
        now=time.monotonic()
        if cached and cached[0]==identity and 0<=now-cached[1]<ttl:
            return cached[2]
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
        after=os.fstat(stream.fileno())
        if identity!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            raise RuntimeError('Executable changed while hashing')
    # Replacing the pathname while the original handle is open must not be cached.
    latest=os.stat(path)
    if identity!=(latest.st_dev,latest.st_ino,latest.st_size,latest.st_mtime_ns,latest.st_ctime_ns):
        raise RuntimeError('Executable replaced while hashing')
    if len(_cache)>8:_cache.clear()
    _cache[key]=(identity,now,digest)
    return digest
