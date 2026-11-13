"""Snapshot the pinned executable's GizSwitch selection slot, read-only.

The slot is an investigation candidate, not a generic nearest-object detector.
No game function calls, injection, or process writes are performed.
"""
import ctypes
import json
from pathlib import Path
import struct
import sys

WORLD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD / 'bridge'))
import diagnose
from inventory_reader import pointer


def main():
    process = next(p for p in diagnose.diagnose()['processes']
                   if p['status'] == 'module_header_read')
    if process['sha256'] != diagnose.RESEARCH_HASH:
        raise ValueError('Unsupported executable')
    kernel = diagnose.bind_kernel()
    handle = kernel.OpenProcess(0x1010, False, process['pid'])
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        read = lambda address, size: diagnose.read_memory(kernel, handle, address, size)
        base = int(process['module_base'], 16)
        manager = pointer(read, base + 0x17EC098)
        if pointer(read, manager) != base + 0xC34AE8:
            raise ValueError('Unexpected GizSwitch manager')
        target = pointer(read, manager + 0x110)
        if not target:
            raise ValueError('No candidate in selection slot')
        data = read(target, 0x400)
        if struct.unpack_from('<Q', data)[0] != base + 0xC34578:
            raise ValueError('Unverified interaction object layout')
        actor = pointer(read, base + 0x1C7D3E0)
        position = struct.unpack('<3f', read(actor + 0x1F0, 12))
        if pointer(read, manager + 0x110) != target or read(target, 0x400) != data:
            raise RuntimeError('Target changed during snapshot; retry')
        flags = struct.unpack_from('<I', data, 0x24C)[0]
        report = dict(writes_enabled=False, pid=process['pid'],
                      manager=hex(manager), target=hex(target),
                      name=data[0x58:0x78].split(b'\0')[0].decode('ascii'),
                      object_origin=struct.unpack_from('<3f', data, 0x78),
                      interaction_position=struct.unpack_from('<3f', data, 0x22C),
                      player_position=position, requirement_flags=hex(flags),
                      explicit_crowbar_item_bit=bool(flags & 0x80000),
                      robber_class_requirement_bit=bool(flags & 0x100),
                      selection_slot_semantics_fully_verified=False,
                      raw_hex=data.hex())
        output = WORLD / 'notes/analysis/live_interaction_target.json'
        output.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in report.items() if k != 'raw_hex'}, indent=2))
    finally:
        kernel.CloseHandle(handle)


if __name__ == '__main__':
    main()
