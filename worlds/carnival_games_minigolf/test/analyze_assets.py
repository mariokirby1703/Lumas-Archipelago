"""Compare local CAR archives without extracting or distributing their contents.

python test/analyze_assets.py USA.CAR PAL.CAR --output comparison.json
"""
import argparse
import ast
import hashlib
import json
import mmap
import re
import struct
from pathlib import Path


class Car:
    def __init__(self, path):
        self.file = Path(path).open('rb')
        self.data = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)
        if self.data[:8] != b'CDGaCube':
            raise ValueError('Not a CDGaCube archive')
        blocks, count, stride = struct.unpack_from('<3I', self.data, 8)
        if stride != 24 or not 20+count*stride < blocks*2048 <= len(self.data):
            raise ValueError('Invalid archive table')
        names = self.data[20+count*stride:blocks*2048].split(b'\0')[:count]
        self.entries = {}
        for i, name in enumerate(names):
            _, _, _, size, index, sector = struct.unpack_from('<6I', self.data, 20+i*stride)
            if index != i or sector*2048+size > len(self.data):
                raise ValueError('Invalid archive entry')
            self.entries[name.decode('ascii')] = (sector*2048, size)

    def read(self, name):
        offset, size = self.entries[name]
        return self.data[offset:offset+size]

    def close(self):
        self.data.close()
        self.file.close()


def compare(usa, pal):
    names = sorted(n for n in usa.entries if n.lower().endswith(('.ini', '.eng', '.cfg', '.xml', '.dat')))
    same = [n for n in names if n in pal.entries and usa.read(n) == pal.read(n)]
    data_ast = ast.parse((Path(__file__).resolve().parents[1]/'data.py').read_text(encoding='utf-8-sig'))
    prizes = next(ast.literal_eval(node.value) for node in data_ast.body
                  if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PRIZES'
                                                         for t in node.targets))
    definitions = dict((int(i), body) for i, body in re.findall(
        r'Elem(\d+)\s*=\s*\{(.*?)\}', usa.read('Data/prizes.ini').decode('cp1252'), re.S))
    mismatches = []
    for prize in prizes:
        body = definitions[prize['id']]
        method = re.search(r'EarnMethod\s*=\s*(\w+)', body)[1]
        kind = ('club' if method == 'Piece' else 'secret' if method == 'Hidden'
                else 'barker_shop' if method == 'BarkerCoin' else 'shop')
        price = int(re.search(r'Misc\s*=\s*(\d+)', body)[1])
        if kind != prize['kind'] or (kind in ('shop', 'barker_shop') and price != prize['price']):
            mismatches.append(prize['id'])
    levels = dict((int(i), body) for i, body in re.findall(
        r'Elem(\d+)\s*=\s*\{(.*?)\}', usa.read('Data/gamelevels.ini').decode('cp1252'), re.S))
    return {'usa_entries': len(usa.entries), 'pal_entries': len(pal.entries),
            'configuration_files_compared': len(names), 'identical_configuration_files': len(same),
            'different_or_missing': [n for n in names if n not in same],
            'prizes_compared': len(prizes), 'prize_kind_or_price_mismatches': mismatches,
            'level_count': len(levels), 'normal_hole_keys_match': all(
                re.search(r'GameName\s*=\s*"([^"]+)"', levels[i])[1] == f'HOLE_{i}_NAME'
                for i in range(27)),
            'critical_assets': {n: {'sha256': hashlib.sha256(usa.read(n)).hexdigest(),
                                    'identical_to_pal': n in same}
                                for n in ('Data/gamelevels.ini', 'Data/prizes.ini', 'Data/TEXT/Games.eng')}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('usa', type=Path)
    parser.add_argument('pal', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    usa, pal = Car(args.usa), Car(args.pal)
    try:
        result = compare(usa, pal)
    finally:
        usa.close()
        pal.close()
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
