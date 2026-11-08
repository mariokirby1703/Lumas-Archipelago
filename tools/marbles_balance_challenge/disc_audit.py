"""Audit locally extracted discs; never copies disc assets into the repository."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import re
import struct
import zlib


def unpack(path):
    data = path.read_bytes()
    count = struct.unpack_from('>I', data)[0]
    offsets = struct.unpack_from(f'>{count}I', data, 4)
    blocks = []
    for offset, end in zip(offsets, (*offsets[1:], len(data))):
        size, codec = struct.unpack_from('>II', data, offset)
        source = data[offset + 8:end]
        if codec == 7:
            result = zlib.decompress(source)
        elif codec == 1:
            result = bytearray()
            ring = bytearray(1024)
            position = 1024 - 66
            cursor = 0
            while len(result) < size:
                flags = source[cursor]
                cursor += 1
                for bit in range(8):
                    if len(result) >= size:
                        break
                    if flags >> bit & 1:
                        values = [source[cursor]]
                        cursor += 1
                        for value in values:
                            result.append(value)
                            ring[position] = value
                            position = (position + 1) & 1023
                    else:
                        low, high = source[cursor:cursor + 2]
                        cursor += 2
                        start = low | ((high & 192) << 2)
                        for index in range((high & 63) + 3):
                            value = ring[(start + index) & 1023]
                            result.append(value)
                            ring[position] = value
                            position = (position + 1) & 1023
        elif codec == 0:
            result = source[:size]
        else:
            raise ValueError(f'{path.name}: unknown codec {codec}')
        if len(result) != size:
            raise ValueError(f'{path.name}: decoded {len(result)} bytes, expected {size}')
        blocks.append(bytes(result))
    return blocks


def dol_word(data, address):
    header = struct.unpack_from('>64I', data)
    for index in range(18):
        offset, base, size = header[index], header[index + 18], header[index + 36]
        if base <= address < base + size:
            return struct.unpack_from('>I', data, offset + address - base)[0]
    raise ValueError(f"Unmapped DOL address: {address:#x}")


def audit(root):
    inventories = {}
    report = {}
    for region in ('PAL', 'NTSC-U'):
        partition = root / region / 'DATA'
        files = partition / 'files'
        inventories[region] = {
            path.relative_to(files).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in files.rglob('*') if path.is_file() and '.svn' not in path.parts
        }
        stages = {}
        for path in sorted((files / 'data').glob('A??S*.bin')):
            text = b'\n'.join(unpack(path)).decode('shift_jis', errors='replace')
            stages[path.stem] = {
                'objects': dict(collections.Counter(re.findall(r'<(EDIT_[A-Z0-9_]+)>', text))),
                'collectibles': dict(collections.Counter(re.findall(r'<model> "EGB_[^"]+" (95|96|97) ', text))),
            }
        dol = (partition / 'sys/main.dol').read_bytes()
        # Save getter, board-record selector and marble inventory accessor.
        sites = ((0x8007552C, 0x80075534, 0x8006E300, 0x80070350) if region == 'PAL'
                 else (0x80075208, 0x80075210, 0x8006E018, 0x8007002C))
        report[region] = {
            'dol_evidence_words': {f'{site:#010x}': f'{dol_word(dol, site):#010x}' for site in sites},
            'game_id': (partition / 'sys/boot.bin').read_bytes()[:6].decode('ascii'),
            'dol_sha256': hashlib.sha256((partition / 'sys/main.dol').read_bytes()).hexdigest(),
            'file_count': len(inventories[region]),
            'stage_objects': stages,
        }
    pal, us = inventories['PAL'], inventories['NTSC-U']
    report['comparison'] = {
        'only_pal': sorted(pal.keys() - us.keys()),
        'only_ntsc_u': sorted(us.keys() - pal.keys()),
        'changed': sorted(name for name in pal.keys() & us.keys() if pal[name] != us[name]),
        'identical': sum(pal[name] == us[name] for name in pal.keys() & us.keys()),
    }
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notes', type=Path, default=Path('worlds/marbles_balance_challenge/notes'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.notes), indent=2) + '\n', encoding='utf-8')
