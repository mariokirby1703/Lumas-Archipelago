from contextlib import ExitStack, contextmanager
import os
from pathlib import Path
import shutil
import tempfile


@contextmanager
def ascii_directory(directory):
    """Give Cygwin WIT a temporary DOS name without moving user files."""
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    query = kernel.QueryDosDeviceW
    query.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD)
    query.restype = wintypes.DWORD
    define = kernel.DefineDosDeviceW
    define.argtypes = (wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR)
    define.restype = wintypes.BOOL
    create_mutex = kernel.CreateMutexW
    create_mutex.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    create_mutex.restype = wintypes.HANDLE
    wait = kernel.WaitForSingleObject
    wait.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    wait.restype = wintypes.DWORD
    release = kernel.ReleaseMutex
    release.argtypes = (wintypes.HANDLE,)
    close = kernel.CloseHandle
    close.argtypes = (wintypes.HANDLE,)
    resolved = str(Path(directory).resolve())
    if resolved.startswith('\\\\?\\'):
        resolved = resolved[4:]
    if resolved.startswith('\\\\'):
        resolved = 'UNC\\' + resolved[2:]
    destination = '\\??\\' + resolved
    buffer = ctypes.create_unicode_buffer(32768)
    for letter in 'ZYXWVUTSRQPONMLKJIHGFED':
        drive = letter + ':'
        mutex = create_mutex(None, False, 'Local\\SonicColoursWITPath' + letter)
        if not mutex:
            continue
        owned = wait(mutex, 0) in (0, 0x80)
        try:
            if not owned or query(drive, buffer, len(buffer)) or ctypes.get_last_error() != 2:
                continue
            if define(1 | 8, drive, destination):
                try:
                    yield Path(drive + '\\')
                finally:
                    # Remove precisely our mapping; never remove another target.
                    if not define(1 | 2 | 4 | 8, drive, destination):
                        import logging
                        logging.getLogger('Client').warning('Could not release temporary WIT path %s', drive)
                return
        finally:
            if owned: release(mutex)
            close(mutex)
    raise OSError('No temporary drive name is available for Wiimms ISO Tools')


@contextmanager
def arguments(executable, args):
    with ExitStack() as stack:
        aliases = {}
        def convert(value):
            text = str(value)
            if os.name != 'nt' or text.isascii() or not Path(text).is_absolute():
                return text
            path = Path(text)
            if not path.name.isascii():
                if not path.is_file():
                    raise OSError('WIT output filenames must be ASCII inside the temporary build')
                directory = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='sonic-wit-')))
                staged = directory / ('input' + path.suffix if path.suffix.isascii() else 'input.bin')
                try:
                    os.link(path, staged)
                except OSError:
                    shutil.copyfile(path, staged)
                return convert(staged)
            parent = path.parent
            tail = [path.name]
            while not parent.is_dir():
                tail.insert(0, parent.name)
                parent = parent.parent
            if parent not in aliases:
                aliases[parent] = stack.enter_context(ascii_directory(parent))
            return str(aliases[parent].joinpath(*tail))
        yield [convert(executable), *(convert(value) for value in args)]
