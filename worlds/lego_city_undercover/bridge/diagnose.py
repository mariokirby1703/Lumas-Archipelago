"""Windows read-only process diagnostics with experimental state readers.

Run directly with 64-bit Python. Does not inject DLLs or modify files/memory.
"""
from __future__ import annotations

import ctypes
import argparse
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path

from research_profile import ABILITY_NAMES, validate_table, decode_ability_query
from objective_reader import read_objectives
from inventory_reader import read_stats, read_characters
from actor_reader import read_actor
from story_reader import read_story

EXE = "LEGOLCUR_DX11.exe"
RESEARCH_HASH = "624fed07274bbd105d1d571ecb97a290df6f6f0aff76898c516890da6d136f76"


class ProcessEntry(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]


class ModuleEntry(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("th32ModuleID", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("GlblcntUsage", wintypes.DWORD),
                ("ProccntUsage", wintypes.DWORD), ("modBaseAddr", ctypes.c_void_p),
                ("modBaseSize", wintypes.DWORD), ("hModule", wintypes.HMODULE),
                ("szModule", wintypes.WCHAR * 256), ("szExePath", wintypes.WCHAR * 260)]


def bind_kernel():
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise OSError("Requires 64-bit Python on Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    signatures = {
        "CreateToolhelp32Snapshot": ([wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
        "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
        "QueryFullProcessImageNameW": ([wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                        ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
        "ReadProcessMemory": ([wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                ctypes.POINTER(ctypes.c_size_t)], wintypes.BOOL),
    }
    for prefix, entry in (("Process32", ProcessEntry), ("Module32", ModuleEntry)):
        for suffix in ("FirstW", "NextW"):
            signatures[prefix + suffix] = ([wintypes.HANDLE, ctypes.POINTER(entry)], wintypes.BOOL)
    for name, (arguments, result) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes = arguments
        function.restype = result
    return kernel


def snapshot_entries(kernel, flags, pid, entry_type, prefix):
    handle = kernel.CreateToolhelp32Snapshot(flags, pid)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry = entry_type()
        entry.dwSize = ctypes.sizeof(entry)
        valid = getattr(kernel, prefix + "FirstW")(handle, ctypes.byref(entry))
        while valid:
            yield entry_type.from_buffer_copy(entry)
            valid = getattr(kernel, prefix + "NextW")(handle, ctypes.byref(entry))
        error = ctypes.get_last_error()
        if error not in (0, 18):  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(error)
    finally:
        kernel.CloseHandle(handle)


def read_memory(kernel, handle, address: int, size: int) -> bytes:
    if not 0x10000 <= address < 0x0000800000000000 or not 0 < size <= 4096:
        raise ValueError("Invalid bounded diagnostic read")
    buffer = ctypes.create_string_buffer(size)
    count = ctypes.c_size_t()
    if not kernel.ReadProcessMemory(handle, address, buffer, size, ctypes.byref(count)):
        raise ctypes.WinError(ctypes.get_last_error())
    if count.value != size:
        raise RuntimeError("Incomplete diagnostic read")
    return buffer.raw


def research_state(kernel, handle, base: int) -> dict:
    """Experimental read of the exact hash's statically referenced ability state.

    Raw arrays have no validated names or gameplay interpretation. Never write them.
    """
    import struct

    table = read_memory(kernel, handle, base + 0x17F84D0, 51 * 4)
    hashes = list(struct.unpack("<51I", table))
    validate_table(hashes)
    pointer = struct.unpack("<Q", read_memory(kernel, handle, base + 0x17EBD48, 8))[0]
    result = dict(evidence="experimental static-reference read", ability_object_pointer=hex(pointer),
                  ability_hash_table=hashes)
    if pointer:
        result["candidate_existing_bytes"] = list(read_memory(kernel, handle, pointer + 0xD8, 51))
        result["candidate_pending_bytes"] = list(read_memory(kernel, handle, pointer + 0x10B, 51))
        result["named_candidate_state"] = {
            name: dict(existing=result["candidate_existing_bytes"][index],
                       pending=result["candidate_pending_bytes"][index])
            for index, name in enumerate(ABILITY_NAMES)
        }
        result["script_query_unlocked"] = decode_ability_query(
            result["candidate_existing_bytes"], result["candidate_pending_bytes"])
        if struct.unpack("<Q", read_memory(kernel, handle, base + 0x17EBD48, 8))[0] != pointer:
            raise RuntimeError("Ability object changed during snapshot; retry")
    return result


def diagnose(include_research_state: bool = False, include_objectives: bool = False,
             include_inventory: bool = False, include_actor: bool = False, include_story: bool = False) -> dict:
    kernel = bind_kernel()
    processes = [entry.th32ProcessID for entry in snapshot_entries(kernel, 2, 0, ProcessEntry, "Process32")
                 if entry.szExeFile.casefold() == EXE.casefold()]
    if not processes:
        return dict(status="game_not_running", gameplay_profile_supported=False, writes_enabled=False)
    results = []
    for pid in processes:
        # PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ; never VM_WRITE/VM_OPERATION.
        handle = kernel.OpenProcess(0x1000 | 0x10, False, pid)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(buffer))
            if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
                raise ctypes.WinError(ctypes.get_last_error())
            path = Path(buffer.value)
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != RESEARCH_HASH:
                results.append(dict(pid=pid, path=str(path), sha256=digest, status="unknown_executable"))
                continue
            modules = list(snapshot_entries(kernel, 8 | 16, pid, ModuleEntry, "Module32"))
            main = next((entry for entry in modules if entry.szModule.casefold() == EXE.casefold()), None)
            if main is None:
                raise RuntimeError("Main module disappeared; retry after scene/process transition")
            header = ctypes.create_string_buffer(64)
            count = ctypes.c_size_t()
            if not kernel.ReadProcessMemory(handle, main.modBaseAddr, header, 64, ctypes.byref(count)):
                raise ctypes.WinError(ctypes.get_last_error())
            if count.value != 64 or header.raw[:2] != b"MZ":
                raise RuntimeError("Unexpected live module header")
            result = dict(pid=pid, path=str(path), sha256=digest, status="module_header_read",
                          module_base=hex(main.modBaseAddr), module_size=main.modBaseSize)
            if include_research_state:
                result["research_state"] = research_state(kernel, handle, main.modBaseAddr)
            if include_objectives:
                result["objectives"] = read_objectives(
                    lambda address, size: read_memory(kernel, handle, address, size), main.modBaseAddr)
            if include_inventory:
                reader = lambda address, size: read_memory(kernel, handle, address, size)
                result["stats"] = read_stats(reader, main.modBaseAddr)
                result["character_inventory"] = read_characters(reader, main.modBaseAddr)
            if include_actor:
                result["actor"] = read_actor(lambda address, size: read_memory(kernel, handle, address, size),
                                             main.modBaseAddr)
            if include_story:
                result["story"] = read_story(lambda address, size: read_memory(kernel, handle, address, size),
                                             main.modBaseAddr)
            results.append(result)
        finally:
            kernel.CloseHandle(handle)
    return dict(processes=results, gameplay_profile_supported=False, writes_enabled=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-state", action="store_true", help="Read experimental named ability state")
    parser.add_argument("--objectives", action="store_true", help="Read experimental city-objective records")
    parser.add_argument("--inventory", action="store_true", help="Read stats and experimental character inventory")
    parser.add_argument("--actor", action="store_true", help="Read active outfit and attached item definitions")
    parser.add_argument("--story", action="store_true", help="Read selected named story Job values")
    args = parser.parse_args()
    try:
        print(json.dumps(diagnose(args.research_state, args.objectives, args.inventory, args.actor, args.story), indent=2))
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps(dict(status="diagnostic_failed", error=str(error), writes_enabled=False)))
        raise SystemExit(1)
