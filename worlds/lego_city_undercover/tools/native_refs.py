"""Find candidate RIP references and direct calls in the pinned local EXE.

Byte-pattern hits require disassembly validation; never executes game code.
"""
import argparse
from pathlib import Path
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from inspect_game import inspect_pe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', type=lambda x: int(x, 0))
    parser.add_argument('--calls', action='store_true')
    args = parser.parse_args()
    world = Path(__file__).resolve().parents[1]
    data = (world / 'notes/gamefiles/LEGOLCUR_DX11.exe').read_bytes()
    pe = inspect_pe(data)
    section = next(s for s in pe['sections'] if s['name'] == '.text')
    code = data[section['raw_offset']:section['raw_offset'] + section['raw_size']]
    decoder = Cs(CS_ARCH_X86, CS_MODE_64)
    lines = []
    for i in range(len(code) - 7):
        rva = section['rva'] + i
        size = 0
        if args.calls and code[i] == 0xe8 and rva + 5 + struct.unpack_from('<i', code, i+1)[0] == args.target:
            size = 5
        elif (not args.calls and code[i] in (0x48, 0x4c) and code[i+1] in (0x8b, 0x8d, 0x89)
              and code[i+2] & 0xc7 == 5 and rva+7+struct.unpack_from('<i', code, i+3)[0] == args.target):
            size = 7
        if size:
            lines.append('\n'.join(f'{x.address:x}: {x.mnemonic} {x.op_str}'
                                   for x in decoder.disasm(code[i:i+64], rva)))
    result = '\n\n'.join(lines)
    (world / f'notes/analysis/refs_{args.target:x}.txt').write_text(result, encoding='utf-8')
    print(result)


if __name__ == '__main__':
    main()
