"""Big-endian, bounds-checked memory access independent of Dolphin's Python module."""
import ctypes
import hashlib
import os
from dataclasses import dataclass
from ctypes import wintypes

from .constants import CODE_SIGNATURES, MANAGER_PTR, SUPPORTED_GAME_ID


class MemoryUnavailable(RuntimeError):
    pass


class WindowsMEM2:
    """Read MEM2 directly when py-dolphin-memory-engine selected a bad Windows mapping."""
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    TH32CS_SNAPPROCESS = 0x00000002
    MEM_COMMIT = 0x1000
    PAGE_GUARD = 0x100
    PAGE_NOACCESS = 0x01
    MEM2_SIZE = 0x04000000

    def __init__(self):
        if os.name == "nt":
            kernel = ctypes.windll.kernel32
            kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.ReadProcessMemory.restype = wintypes.BOOL
            kernel.VirtualQueryEx.restype = ctypes.c_size_t
        self.session = None
        self.process = None
        self.base = None
        self.error = "not probed"

    def set_session(self, session):
        if session != self.session:
            self.close()
            self.session = session

    def close(self):
        if self.process:
            ctypes.windll.kernel32.CloseHandle(self.process)
        self.process = None
        self.base = None

    @staticmethod
    def _process_ids():
        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]
        kernel = ctypes.windll.kernel32
        snapshot = kernel.CreateToolhelp32Snapshot(WindowsMEM2.TH32CS_SNAPPROCESS, 0)
        if snapshot == wintypes.HANDLE(-1).value:
            return []
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        result = []
        try:
            present = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
            while present:
                if entry.szExeFile.lower() in {"dolphin.exe", "dolphinqt2.exe"}:
                    result.append(entry.th32ProcessID)
                present = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel.CloseHandle(snapshot)
        return result

    @staticmethod
    def _read_process(process, address, size):
        buffer = ctypes.create_string_buffer(size)
        read = ctypes.c_size_t()
        ok = ctypes.windll.kernel32.ReadProcessMemory(
            process, ctypes.c_void_p(address), buffer, size, ctypes.byref(read))
        if not ok or read.value != size:
            raise OSError(ctypes.get_last_error(), "ReadProcessMemory failed")
        return buffer.raw

    def _valid_session(self, process, base):
        offset = self.session - 0x90000000
        if not 0 <= offset <= self.MEM2_SIZE - 0x2F4:
            return False
        player = int.from_bytes(self._read_process(process, base + offset + 0x2EC, 4), "big")
        course = int.from_bytes(self._read_process(process, base + offset + 0x2F0, 4), "big")
        controller = int.from_bytes(self._read_process(process, base + offset + 0xFC, 4), "big")
        if player not in (0, 1) or not 0 <= course < 27 or not valid_pointer(controller, 0x20):
            return False
        controller_offset = controller - 0x90000000
        if not 0 <= controller_offset <= self.MEM2_SIZE - 0x20:
            return False
        vtable = int.from_bytes(self._read_process(process, base + controller_offset + 0x1C, 4), "big")
        return 0x80004000 <= vtable < 0x81800000

    def _discover(self):
        if os.name != "nt" or self.session is None:
            raise OSError("Windows MEM2 fallback has no live session")

        class MEMORY_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [("BaseAddress", ctypes.c_void_p), ("AllocationBase", ctypes.c_void_p),
                        ("AllocationProtect", wintypes.DWORD), ("PartitionId", wintypes.WORD),
                        ("RegionSize", ctypes.c_size_t), ("State", wintypes.DWORD),
                        ("Protect", wintypes.DWORD), ("Type", wintypes.DWORD)]

        kernel = ctypes.windll.kernel32
        for pid in self._process_ids():
            process = kernel.OpenProcess(self.PROCESS_QUERY_INFORMATION | self.PROCESS_VM_READ, False, pid)
            if not process:
                continue
            address = 0
            info = MEMORY_BASIC_INFORMATION()
            try:
                while kernel.VirtualQueryEx(process, ctypes.c_void_p(address), ctypes.byref(info),
                                            ctypes.sizeof(info)):
                    base = int(info.BaseAddress or 0)
                    size = int(info.RegionSize)
                    readable = (info.State == self.MEM_COMMIT and not info.Protect & self.PAGE_GUARD
                                and info.Protect & 0xFF != self.PAGE_NOACCESS)
                    if readable and size >= self.MEM2_SIZE:
                        try:
                            if self._valid_session(process, base):
                                self.process, self.base = process, base
                                self.error = None
                                return
                        except OSError:
                            pass
                    next_address = base + size
                    if next_address <= address:
                        break
                    address = next_address
            finally:
                if self.process != process:
                    kernel.CloseHandle(process)
        self.error = "no Dolphin MEM2 mapping matched the live session"
        raise OSError(self.error)

    def read(self, address, size):
        if self.base is None:
            self._discover()
        try:
            return self._read_process(self.process, self.base + address - 0x90000000, size)
        except OSError as error:
            self.error = str(error)
            self.close()
            raise


def valid_pointer(address, size=4):
    return (isinstance(address, int) and address % 4 == 0 and
            (0x80004000 <= address <= 0x81800000 - size or
             0x90000000 <= address <= 0x94000000 - size))


class Memory:
    def __init__(self, backend, mem2_backend=None):
        self.backend = backend
        self.mem2_backend = mem2_backend if mem2_backend is not None else (WindowsMEM2() if os.name == "nt" else None)
        self.last_read_error = None

    def read(self, address, size):
        if not (0x80000000 <= address <= 0x81800000 - size or
                0x90000000 <= address <= 0x94000000 - size):
            raise MemoryUnavailable(f"Address outside Wii RAM: {address:#x}")
        try:
            data = bytes(self.backend.read_bytes(address, size))
        except (RuntimeError, OSError) as error:
            self.last_read_error = f"{type(error).__name__}: {error}"
            if address >= 0x90000000 and self.mem2_backend is not None:
                try:
                    data = self.mem2_backend.read(address, size)
                except (RuntimeError, OSError) as fallback_error:
                    self.last_read_error += f"; MEM2 fallback: {type(fallback_error).__name__}: {fallback_error}"
                    raise MemoryUnavailable(
                        f"Dolphin memory read failure at {address:#010x}: {self.last_read_error}") from fallback_error
            else:
                raise MemoryUnavailable(
                    f"Dolphin memory read failure at {address:#010x}: {self.last_read_error}") from error
        if len(data) != size:
            raise MemoryUnavailable("Short Dolphin read")
        return data

    def integer(self, address, size=4):
        return int.from_bytes(self.read(address, size), 'big')

    def pointer(self, address, size=4):
        value = self.integer(address)
        if not valid_pointer(value, size):
            raise MemoryUnavailable(f"Uninitialized or invalid pointer at {address:#x}")
        return value

    def write(self, address, data):
        if self.read(address, len(data)) != data:
            self.backend.write_bytes(address, data)
            if self.read(address, len(data)) != data:
                raise MemoryUnavailable("Dolphin write could not be verified")

    def put(self, address, value, size=1):
        self.write(address, value.to_bytes(size, 'big'))

    def verify_game(self):
        return (self.read(0x80000000, 6) == SUPPORTED_GAME_ID and
                all(hashlib.sha256(self.read(address, 64)).hexdigest() == digest
                    for address, digest in CODE_SIGNATURES))

    def resolve(self, local_player=0):
        manager = self.pointer(MANAGER_PTR, 0x1A0)
        session = self.integer(manager + 0x114)
        if not valid_pointer(session, 0x2F4):
            session = None
        if self.mem2_backend is not None:
            self.mem2_backend.set_session(session)
        # manager+0x12C is not a reliable player count in every game state.
        root_values = tuple(self.integer(manager + 0x190 + i*4) for i in range(2))
        valid_roots = tuple((i, root) for i, root in enumerate(root_values) if valid_pointer(root, 0x2E0))
        if not valid_roots:
            raise MemoryUnavailable("Waiting for game player state.")
        selected = next(((i, root) for i, root in valid_roots if i == local_player), None)
        if selected is None:
            raise MemoryUnavailable("Waiting for configured game player state.")
        selected_player, selected_root = selected
        roots = tuple(dict.fromkeys(root for _, root in valid_roots))
        return Snapshot(manager, roots, selected_root, session, selected_player, local_player)

    def confirm(self, snapshot):
        current = self.resolve(snapshot.requested_player)
        if (current.manager, current.root, current.session) != (snapshot.manager, snapshot.root, snapshot.session):
            raise MemoryUnavailable("Player context changed during poll")


@dataclass(frozen=True)
class Snapshot:
    manager: int
    roots: tuple[int, ...]
    root: int
    session: int | None
    local_player: int
    requested_player: int
