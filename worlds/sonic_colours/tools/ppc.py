"""Local PAL ELF inspection; the executable is never packaged or modified."""
import argparse
from pathlib import Path
import struct


class Executable:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        if self.data[:7] != b'\x7fELF\x01\x02\x01':
            raise ValueError('expected big-endian ELF32')
        start = struct.unpack_from('>I', self.data, 32)[0]
        stride, count = struct.unpack_from('>HH', self.data, 46)
        self.sections = [struct.unpack_from('>10I', self.data, start + i * stride) for i in range(count)]

    def read(self, address, size):
        section = next(s for s in self.sections if s[1] == 1 and s[3] <= address < address + size <= s[3] + s[5])
        offset = section[4] + address - section[3]
        return self.data[offset:offset + size]

    def disassemble(self, start, size):
        from capstone import Cs, CS_ARCH_PPC, CS_MODE_32, CS_MODE_BIG_ENDIAN
        decoder = Cs(CS_ARCH_PPC, CS_MODE_32 | CS_MODE_BIG_ENDIAN)
        decoder.skipdata = True  # Wii paired-single instructions may be unsupported.
        return decoder.disasm(self.read(start, size), start)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('address', type=lambda v: int(v, 0))
    parser.add_argument('size', type=lambda v: int(v, 0))
    parser.add_argument('--elf', type=Path, default=Path(__file__).parents[1] / 'notes/Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf')
    args = parser.parse_args()
    for instruction in Executable(args.elf).disassemble(args.address, args.size):
        print(f'{instruction.address:08X}: {instruction.mnemonic:9} {instruction.op_str}')
