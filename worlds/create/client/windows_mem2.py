"""Fallback for DME's Windows MEM2 search stopping before Dolphin's fastmem views.

Use only a mapped MEM2 view exactly 256 MiB above a verified MEM1 alias.
Never select unrelated allocations merely because they happen to be 64 MiB.
"""
from __future__ import annotations

import ctypes as c
from ctypes import wintypes as w
import os


class MemoryRegion(c.Structure):
    _fields_ = [
        ("base", c.c_void_p), ("allocation_base", c.c_void_p),
        ("allocation_protect", w.DWORD), ("partition", w.WORD),
        ("size", c.c_size_t), ("state", w.DWORD), ("protect", w.DWORD), ("kind", w.DWORD),
    ]


class ProcessEntry(c.Structure):
    _fields_ = [
        ("size", w.DWORD), ("usage", w.DWORD), ("pid", w.DWORD),
        ("heap", c.c_size_t), ("module", w.DWORD), ("threads", w.DWORD),
        ("parent", w.DWORD), ("priority", w.LONG), ("flags", w.DWORD),
        ("exe", w.WCHAR * 260),
    ]


def mapped_ram(region: MemoryRegion, size: int) -> bool:
    return (region.size == size and region.state == 0x1000 and region.kind == 0x40000
            and region.protect & 0xFF == 0x04 and not region.protect & 0x100)


class WindowsMEM2:
    def __init__(self, engine, *, writable: bool = True):
        self.handle = None
        self.base = 0
        self.kernel = k = c.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "OpenProcess": ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
            "CloseHandle": ([w.HANDLE], w.BOOL),
            "CreateToolhelp32Snapshot": ([w.DWORD, w.DWORD], w.HANDLE),
            "Process32FirstW": ([w.HANDLE, c.POINTER(ProcessEntry)], w.BOOL),
            "Process32NextW": ([w.HANDLE, c.POINTER(ProcessEntry)], w.BOOL),
            "VirtualQueryEx": ([w.HANDLE, c.c_void_p, c.POINTER(MemoryRegion), c.c_size_t], c.c_size_t),
            "ReadProcessMemory": ([w.HANDLE, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)], w.BOOL),
            "WriteProcessMemory": ([w.HANDLE, c.c_void_p, c.c_void_p, c.c_size_t, c.POINTER(c.c_size_t)], w.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(k, name)
            function.argtypes, function.restype = args, result
        # Only compare the immutable disc ID. The low-memory header also contains
        # live OS values (0xC0..0xE7) that change between two reads.
        reference = engine.read_bytes(0x80000000, 6)
        if reference[:6] != b"SECP69":
            raise RuntimeError("MEM2 fallback requires Create SECP69.")
        snapshot = k.CreateToolhelp32Snapshot(2, 0)
        if snapshot == c.c_void_p(-1).value:
            raise OSError(c.get_last_error(), "Cannot enumerate Dolphin")
        pids = []
        try:
            entry = ProcessEntry()
            entry.size = c.sizeof(entry)
            found = k.Process32FirstW(snapshot, c.byref(entry))
            custom = os.environ.get("DME_DOLPHIN_PROCESS_NAME")
            names = {custom.lower(), custom.lower() + ".exe"} if custom else {
                "dolphin.exe", "dolphinqt2.exe", "dolphinwx.exe"}
            while found:
                if entry.exe.lower() in names:
                    pids.append(entry.pid)
                found = k.Process32NextW(snapshot, c.byref(entry))
        finally:
            k.CloseHandle(snapshot)
        # DME exposes no PID. Refuse ambiguity rather than write to another emulator.
        if len(pids) != 1:
            raise RuntimeError("MEM2 fallback requires exactly one Dolphin process.")
        self.handle = k.OpenProcess(0x410 | (0x28 if writable else 0), False, pids[0])
        if not self.handle:
            raise OSError(c.get_last_error(), "Cannot open Dolphin")
        try:
            address = 0
            region = MemoryRegion()
            while k.VirtualQueryEx(self.handle, address, c.byref(region), c.sizeof(region)):
                base = region.base or 0
                if mapped_ram(region, 0x2000000):
                    try:
                        matches = self._read(base, len(reference)) == reference
                    except OSError:
                        matches = False
                    if matches:
                        mem2 = MemoryRegion()
                        candidate = base + 0x10000000
                        if (k.VirtualQueryEx(self.handle, candidate, c.byref(mem2), c.sizeof(mem2))
                                and mem2.base == candidate and mapped_ram(mem2, 0x4000000)):
                            self._read(candidate, 4)
                            self.base = candidate
                            return
                address = base + region.size
            raise RuntimeError("No verified Dolphin MEM1/MEM2 alias pair found.")
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None
        self.base = 0

    def _read(self, address: int, size: int) -> bytes:
        buffer = c.create_string_buffer(size)
        transferred = c.c_size_t()
        if (not self.kernel.ReadProcessMemory(self.handle, address, buffer, size, c.byref(transferred))
                or transferred.value != size):
            raise OSError(c.get_last_error(), "Dolphin MEM2 read failed")
        return buffer.raw

    def _address(self, address: int, size: int) -> int:
        if not self.handle or not self.base or not 0x90000000 <= address < address + size <= 0x94000000:
            raise ValueError("MEM2 access outside the verified mapping")
        return self.base + address - 0x90000000

    def read(self, address: int, size: int) -> bytes:
        return self._read(self._address(address, size), size)

    def write(self, address: int, data: bytes) -> None:
        target = self._address(address, len(data))
        transferred = c.c_size_t()
        buffer = c.create_string_buffer(data)
        if (not self.kernel.WriteProcessMemory(self.handle, target, buffer, len(data), c.byref(transferred))
                or transferred.value != len(data)):
            raise OSError(c.get_last_error(), "Dolphin MEM2 write failed")
