"""Native null-path regression; offline instruction execution, not Dolphin."""

from ..tools.private_assets import reference_root
from pathlib import Path
import struct
import pytest
from ..client import map_transition as t


@pytest.mark.parametrize('phase', ['cleanup', 'update'])
@pytest.mark.parametrize('path', [0, 0x90B51000])
def test_optional_path_cleanup(path, phase):
    update = phase == 'update'
    hook, original, destination_pc = (t.UPDATE_HOOK, t.UPDATE_ORIGINAL, t.NEXT_STATE) if update else (t.HOOK, t.ORIGINAL, t.CLEANUP)
    output = 6 if update else 3
    words = t.update_payload() if update else t.payload()
    r = list(range(32)); r[4] = 0x90B50000
    pc = 0; equal = False; ctr = None; destination = None
    for _ in range(10):
        w = words[pc]; pc += 1
        if w == original:
            r[output] = path
        elif w in (0x2C030000, 0x2C060000):
            equal = r[output] == 0
        elif w == 0x40820014:
            if not equal: pc += 4
        elif w == 0x3D808026: r[12] = 0x80260000
        elif w in (0x618CC984, 0x618CCB6C): r[12] |= w & 0xffff
        elif w == 0x7D8903A6: ctr = r[12]
        elif w == 0x4E800420:
            destination = ctr; break
        elif w == 0:
            destination = hook + 4; break
        else: raise AssertionError(hex(w))
    assert destination == (destination_pc if path == 0 else hook + 4)
    assert r[output] == path
    assert all(r[i] == i for i in range(32) if i not in (output, 4, 12))
    assert r[4] == 0x90B50000


def test_pal_displaced_instruction_and_cleanup():
    from ..tools.ppc import Executable
    p = reference_root()/'Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not p.exists(): pytest.skip('Original PAL executable unavailable')
    e = Executable(p)
    assert e.read(t.HOOK, 8) == bytes.fromhex('806407EC80030008')
    assert e.read(t.UPDATE_HOOK, 4) == t.UPDATE_ORIGINAL.to_bytes(4, 'big')
    assert e.read(0x8026CA2C, 4) == bytes.fromhex('80060008')
    assert e.read(t.NEXT_STATE, 4) == bytes.fromhex('3CE08077')
    # Original cleanup sets animation phase to zero, then returns normally.
    assert e.read(t.CLEANUP, 8) == bytes.fromhex('38000000901F068C')


@pytest.mark.parametrize('phase', ['cleanup', 'update'])
@pytest.mark.parametrize('mutation', ['none', 'payload', 'return', 'other_text'])
def test_full_pal_revision_accepts_only_exact_optional_path_hook(mutation, phase):
    from ..tools.ppc import Executable
    from ..client.versions import VERSION, verify_revision
    from ..client.memory import SonicMemory, MemoryUnavailable
    p = reference_root()/'Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not p.exists(): pytest.skip('Original PAL executable unavailable')
    e = Executable(p)
    regions = {0x80000000: bytearray(b'SNCP8P\0\0')}
    for section in VERSION['text_sections']:
        regions[section['address']] = bytearray(e.read(section['address'], section['size']))
    target = 0x80003000
    hook, original = (t.UPDATE_HOOK, t.UPDATE_ORIGINAL) if phase == 'update' else (t.HOOK, t.ORIGINAL)
    words = t.update_payload() if phase == 'update' else t.payload()
    words[-1] = 0x48000000 | ((hook+4-(target+len(words)*4-4)) & 0x03fffffc)
    regions[target-8] = bytearray(struct.pack('>2I', 0xC2000000 | (hook-0x80000000), len(words)//2))
    regions[target] = bytearray(struct.pack('>'+'I'*len(words), *words))
    section = next(s for s in VERSION['text_sections'] if s['address'] <= hook < s['address']+s['size'])
    offset = hook-section['address']
    struct.pack_into('>I', regions[section['address']], offset,
                     0x48000000 | ((target-hook) & 0x03fffffc))
    if mutation == 'payload': regions[target][7] ^= 1
    if mutation == 'return': regions[target][-1] ^= 4
    if mutation == 'other_text': regions[section['address']][4] ^= 1
    class Backend:
        def read_bytes(self, address, size):
            for base, data in regions.items():
                if base <= address and address+size <= base+len(data):
                    return bytes(data[address-base:address-base+size])
            return bytes(size)
        def write_bytes(self, *args):
            raise AssertionError('revision verification must never write')
    memory = SonicMemory(Backend())
    if mutation == 'none':
        assert (t.update_installed(memory) if phase == 'update' else t.installed(memory))
        assert verify_revision(memory) == VERSION['dol_sha256']
        assert memory.revision_observation['verified']
    else:
        with pytest.raises(MemoryUnavailable, match='unknown_revision'):
            verify_revision(memory)
        assert not memory.revision_observation['verified']
