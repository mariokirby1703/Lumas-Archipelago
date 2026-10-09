"""Read every supplied file, validate structured catalogs and PPC cross-references.

Uses the local dev-only ELF wrapper; never ships or executes Wii code. The old
research scripts require missing /mnt/data inputs and are inspected, not run.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import struct


def audit():
    root = Path(__file__).resolve().parents[1]
    notes = root / 'notes'
    entries = []
    for path in sorted(notes.rglob('*')):
        if not path.is_file():
            continue
        data = path.read_bytes()
        entry = {'path': path.relative_to(notes).as_posix(), 'size': len(data),
                 'sha256': hashlib.sha256(data).hexdigest()}
        if path.suffix == '.json':
            content = json.loads(data.decode('utf-8-sig'))
            entry['records'] = len(content)
        elif path.suffix == '.csv':
            content = list(csv.DictReader(data.decode('utf-8-sig').splitlines()))
            entry['records'] = len(content)
            entry['columns'] = list(content[0])
        elif path.suffix != '.elf':
            content = data.decode('utf-8-sig')
            entry['lines'] = len(content.splitlines())
        entries.append(entry)
    static = notes / 'Sonic_Colours_PAL_Static_RE_v2'
    handoff = notes / 'Sonic_Colours_Wii_PAL_Codex_Handoff'
    assert (notes / 'SONIC_COLOURS_WII_PAL_CODEX_MASTER_SPEC.md').read_bytes() == (
        handoff / 'SONIC_COLOURS_WII_PAL_CODEX_MASTER_SPEC.md').read_bytes()
    for path in (handoff / 'research/static_re').iterdir():
        if (static / path.name).is_file():
            assert path.read_bytes() == (static / path.name).read_bytes(), path.name
    elf = (static / 'sonic_pal_disassembly.elf').read_bytes()
    assert elf[:7] == b'\x7fELF\x01\x02\x01'
    section_offset = struct.unpack_from('>I', elf, 32)[0]
    section_size, count = struct.unpack_from('>HH', elf, 46)
    sections = []
    for i in range(count):
        _, kind, flags, address, offset, size, _, _, _, _ = struct.unpack_from(
            '>10I', elf, section_offset + i * section_size)
        if kind == 1:
            sections.append((address, offset, size, flags))

    def read(address, size=4):
        base, offset, _, _ = next(s for s in sections if s[0] <= address < address + size <= s[0] + s[2])
        return elf[offset + address - base:offset + address - base + size]

    def word(address):
        return int.from_bytes(read(address), 'big')

    instruction_count = 0
    for path in (static / 'annotated_disassembly.txt', handoff / 'research/static_re/bitfield_helpers_disasm.txt'):
        for address, opcode in re.findall(r'^([0-9a-f]{8}):\s+((?:[0-9a-f]{2} ){3}[0-9a-f]{2})',
                                          path.read_text(), re.MULTILINE):
            assert read(int(address, 16)) == bytes.fromhex(opcode), (path.name, address)
            instruction_count += 1
    for hook in json.loads((static / 'gecko_hooks_static.json').read_text()):
        for address, opcode in hook['near']:
            assert word(int(address, 16)) == int(opcode, 16)
    calls = json.loads((handoff / 'research/static_re/direct_calls.json').read_text())
    call_count = 0
    for target, callers in calls.items():
        for caller in callers:
            pc = int(caller, 16)
            opcode = word(pc)
            assert opcode >> 26 == 18 and opcode & 1
            displacement = opcode & 0x03fffffc
            if displacement & 0x02000000:
                displacement -= 0x04000000
            destination = displacement if opcode & 2 else pc + displacement
            assert destination == int(target, 16)
            call_count += 1
    assert read(0x80004294, 8).hex() == '3da0808f61ad9520'
    assert word(0x80160c10) == 0x806da108
    assert word(0x8015fa1c) == 0x3c600002 and word(0x8015fa20) == 0x38039608
    assert word(0x8015f940) == 0x80630000 and word(0x8015f944) == 0x3863001c
    assert word(0x80055e98) == 0x80de0018
    assert word(0x8027e744) == 0x881f0120 and word(0x800381c4) == 0x80030010
    versions = json.loads((root / 'data/versions.json').read_text())
    for section in versions['text_sections']:
        assert hashlib.sha256(read(section['address'], section['size'])).hexdigest() == section['sha256']
    report = {'files': entries, 'file_count': len(entries), 'validated_disassembly_instructions': instruction_count,
              'validated_direct_calls': call_count, 'r13_initialization': '0x808F9520',
              'manager_global_candidate': '0x808F3628', 'live_validation': False,
              'missing_inputs': ['original main.dol', 'CPK and Lua originals/asset index', 'raw MEM1/MEM2 captures'],
              'runtime_dependencies_on_notes': False}
    destination = root / 'docs/research_audit.json'
    destination.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'{len(entries)} files read; {instruction_count} disassembled instructions; '
          f'{call_count} direct calls verified against ELF. No live proof implied.')


if __name__ == '__main__':
    audit()
