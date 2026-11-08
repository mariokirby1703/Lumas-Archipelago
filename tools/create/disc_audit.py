"""Audit locally supplied CREATE discs; never extract or redistribute game assets.

Run from the repository root: python tools/create/disc_audit.py
Only Python's standard library is required. Output contains metadata and hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def elf(path: Path):
    data = path.read_bytes()
    if data[:6] != b'\x7fELF\x01\x02':
        raise ValueError(f'Expected big-endian ELF32: {path}')
    header = struct.unpack_from('>16sHHIIIIIHHHHHH', data)
    offset, stride, count = header[6], header[11], header[12]
    sections = [struct.unpack_from('>10I', data, offset + i * stride) for i in range(count)]
    symbols = {}
    for section in sections:
        if section[1] != 2:
            continue
        strings_section = sections[section[6]]
        strings = data[strings_section[4]:strings_section[4] + strings_section[5]]
        for pos in range(section[4], section[4] + section[5], section[9]):
            name, value, size, _, _, index = struct.unpack_from('>IIIBBH', data, pos)
            if name and index:
                label = strings[name:strings.index(0, name)].decode('utf-8')
                symbols[label] = (value, size, index)
    return data, sections, symbols


def at(image, address: int, size: int) -> bytes:
    data, sections, _ = image
    for section in sections:
        if section[1] != 8 and section[3] <= address and address + size <= section[3] + section[5]:
            offset = section[4] + address - section[3]
            return data[offset:offset + size]
    raise ValueError(f'Address not file-backed: 0x{address:08X}')


def big(path: Path) -> dict[str, bytes]:
    data = path.read_bytes()
    if data[:4] not in (b'BIGF', b'BIG4'):
        raise ValueError(f'Expected BIGF/BIG4: {path}')
    count = struct.unpack_from('>I', data, 8)[0]
    pos, entries = 16, {}
    for _ in range(count):
        offset, size = struct.unpack_from('>II', data, pos)
        end = data.index(0, pos + 8)
        name = data[pos + 8:end].decode('utf-8')
        if offset + size > len(data):
            raise ValueError(f'Truncated BIGF entry: {path}: {name}')
        entries[name] = data[offset:offset + size]
        pos = end + 1
    return entries


def refpack(data: bytes) -> bytes:
    """Decode the EA RefPack headers present in these RPK entries."""
    if data[:2] not in (b'\x10\xfb', b'\x15\xfb'):
        return data
    width = 4 if data[0] == 0x15 else 3
    expected = int.from_bytes(data[2:2 + width], 'big')
    pos, output = 2 + width, bytearray()
    while pos < len(data):
        control = data[pos]
        pos += 1
        if control >= 252:
            literals = control & 3
            output.extend(data[pos:pos + literals])
            break
        if control >= 224:
            literals, count, offset = ((control & 31) << 2) + 4, 0, 0
        elif control >= 192:
            a, b, c = data[pos:pos + 3]
            pos += 3
            literals = control & 3
            count = ((control & 12) << 6) + c + 5
            offset = ((control & 16) << 12) + (a << 8) + b + 1
        elif control >= 128:
            a, b = data[pos:pos + 2]
            pos += 2
            literals, count = a >> 6, (control & 63) + 4
            offset = ((a & 63) << 8) + b + 1
        else:
            a = data[pos]
            pos += 1
            literals, count = control & 3, ((control & 28) >> 2) + 3
            offset = ((control & 96) << 3) + a + 1
        output.extend(data[pos:pos + literals])
        pos += literals
        for _ in range(count):
            output.append(output[-offset])
        if len(output) > expected:
            raise ValueError('RefPack output exceeds declared size')
    if len(output) != expected:
        raise ValueError('RefPack output size mismatch')
    return bytes(output)


def compare_entries(left, right):
    return {name: ('equal' if left.get(name) == right.get(name) else
                   'different' if name in left and name in right else 'region_only')
            for name in sorted(left.keys() | right.keys())}


def audit(root: Path, notes: Path):
    images = [elf(notes / region / 'DATA/files/hp_r.elf') for region in ('PAL', 'NTSC-U')]
    pal, usa = images
    sections = []
    for left, right in zip(pal[1], usa[1]):
        if not left[2] & 2 or not left[5]:
            continue
        backed = left[1] != 8
        a = at(pal, left[3], left[5]) if backed else b''
        b = at(usa, right[3], right[5]) if backed else b''
        sections.append({'address': f'0x{left[3]:08X}', 'size': left[5],
                         'layout_equal': left == right, 'file_backed': backed, 'executable': bool(left[2] & 4),
                         'different_bytes': [f'0x{left[3] + i:08X}' for i, (x, y) in enumerate(zip(a, b)) if x != y],
                         'pal_sha256': sha256(a) if backed else None,
                         'ntsc_u_sha256': sha256(b) if backed else None})
    dol = (notes / 'NTSC-U/DATA/sys/main.dol').read_bytes()
    dol_sections = []
    for i in range(18):
        offset, address, size = [struct.unpack_from('>I', dol, base + 4 * i)[0] for base in (0, 0x48, 0x90)]
        if size:
            # DOL pads ELF sections to 32-byte boundaries.
            section = next(s for s in usa[1] if s[3] == address and s[1] != 8)
            payload = at(usa, address, section[5])
            dol_sections.append({'address': f'0x{address:08X}', 'size': size,
                                 'elf_payload_equal': dol[offset:offset + len(payload)] == payload})
    # Import only this standalone module, without loading the Archipelago world.
    namespace = {'__name__': 'create_popup_audit'}
    import sys
    import types
    module = types.ModuleType(namespace['__name__'])
    sys.modules[module.__name__] = module
    exec(compile((root / 'worlds/create/client/popup_runtime.py').read_text(), 'popup_runtime.py', 'exec'), module.__dict__)
    originals = {**module.ORIGINALS, **module.LEGACY_ORIGINALS}
    ram = json.loads((root / 'worlds/create/data/ram_map.json').read_text())
    patch = ram['object_system']['contraption_patch']
    originals[int(patch['address'], 0)] = int(patch['original'], 0)
    checks = {f'0x{address:08X}': all(at(image, address, 4) == struct.pack('>I', value) for image in images)
              for address, value in originals.items()}
    layout = module.PopupPatchLayout()
    caves = {f'0x{start:08X}': all(at(image, start, end - start) == bytes(end - start) for image in images)
             for start, end in ((layout.code_base, layout.end), (layout.aux_base, layout.aux_end))}
    archives = [big(notes / region / 'DATA/files/data.big') for region in ('PAL', 'NTSC-U')]
    entries = compare_entries(*archives)
    unpacked = {}
    for name, status in entries.items():
        if status == 'different':
            a, b = [refpack(archive[name]) for archive in archives]
            differences = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
            unpacked[name] = {'pal_size': len(a), 'ntsc_u_size': len(b),
                              'different_byte_count': len(differences),
                              'first_difference': hex(differences[0]) if differences else None,
                              'last_difference': hex(differences[-1]) if differences else None}
    files = []
    for path in sorted((notes / 'PAL/DATA/files').rglob('*')):
        if path.is_file():
            relative = path.relative_to(notes / 'PAL/DATA/files')
            other = notes / 'NTSC-U/DATA/files' / relative
            archive_entries = compare_entries(big(path), big(other)) if path.suffix == '.big' and other.exists() else None
            if archive_entries is not None:
                archive_entries = {'counts': {status: list(archive_entries.values()).count(status)
                                             for status in ('equal', 'different', 'region_only')},
                                   'differences': {name: status for name, status in archive_entries.items() if status != 'equal'}}
            files.append({'archive_entries': archive_entries, 'path': relative.as_posix(), 'pal_size': path.stat().st_size,
                          'ntsc_u_size': other.stat().st_size if other.exists() else None,
                          'equal': other.exists() and sha256(path.read_bytes()) == sha256(other.read_bytes())})
    return {'elf_symbols': len(pal[2]), 'all_symbols_equal': pal[2] == usa[2],
            'elf_sha256': [sha256(image[0]) for image in images], 'sections': sections,
            'ntsc_u_disc_id': (notes / 'NTSC-U/DATA/sys/boot.bin').read_bytes()[:6].decode('ascii'),
            'ntsc_u_dol_sections': dol_sections, 'patch_originals_match_both_regions': checks,
            'patch_caves_zero_both_regions': caves, 'data_big_entries': entries,
            'changed_data_big_entries_decompressed': unpacked, 'files': files}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notes', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    report = audit(root, args.notes or root / 'worlds/create/notes')
    rendered = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.write_text(rendered, encoding='utf-8')
    else:
        print(rendered, end='')
    valid = (report['all_symbols_equal'] and report['ntsc_u_disc_id'] == 'SECE69'
             and all(s['layout_equal'] for s in report['sections'])
             and all(not s['different_bytes'] for s in report['sections'] if s['executable'])
             and {address for s in report['sections'] for address in s['different_bytes']}
             == {'0x805F7409', '0x805F740A', '0x805F7438', '0x805F743A', '0x805F743B'}
             and all(s['elf_payload_equal'] for s in report['ntsc_u_dol_sections'])
             and all(report['patch_originals_match_both_regions'].values())
             and all(report['patch_caves_zero_both_regions'].values()))
    raise SystemExit(0 if valid else 1)
