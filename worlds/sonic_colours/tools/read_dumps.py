"""Exercise production native readers against private, original capture pairs."""
import argparse
import json
import os
from pathlib import Path
import sys
import unittest  # activates repository world filter

os.environ['AP_TEST_WORLDS'] = 'sonic_colours'
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from worlds.sonic_colours.client.memory import SonicMemory, MemoryUnavailable
from worlds.sonic_colours.client.native_read import read_saved_progress, read_stage_objects
from worlds.sonic_colours.world_constants import load_data


class DumpBackend:
    def __init__(self, mem1, mem2):
        self.pools = [(0x80000000, Path(mem1).read_bytes()), (0x90000000, Path(mem2).read_bytes())]

    def read_bytes(self, address, size):
        for base, data in self.pools:
            if base <= address < address + size <= base + len(data):
                return data[address - base:address - base + size]
        raise MemoryUnavailable('dump_range_unavailable')

    def write_bytes(self, address, data):
        raise MemoryUnavailable('original_dump_is_read_only')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = []
    for directory in sorted(p for p in args.root.iterdir() if p.is_dir()):
        mem1 = sorted(directory.glob('mem1*.raw'))
        mem2 = sorted(directory.glob('mem2*.raw'))
        if len(mem1) != len(mem2):
            raise ValueError('unpaired capture directory')
        for first, second in zip(mem1, mem2):
            memory = SonicMemory(DumpBackend(first, second))
            row = {'mem1': first.name, 'mem2': second.name, 'simultaneous': False}
            for name, reader in [('stage_objects', lambda: read_stage_objects(memory)),
                                 ('saved_progress', lambda: read_saved_progress(memory, load_data('progress_bits.json')))]:
                try:
                    row[name] = reader()
                except MemoryUnavailable as error:
                    row[name + '_error'] = str(error)
            output.append(row)
    args.output.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    for row in output:
        print(row['mem1'], row.get('stage_objects', row.get('stage_objects_error')),
              row.get('saved_progress_error', 'saved progress decoded'))
