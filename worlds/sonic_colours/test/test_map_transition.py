"""Native null-path regression; offline instruction execution, not Dolphin."""
from pathlib import Path
import pytest
from ..client import map_transition as t


@pytest.mark.parametrize('path', [0, 0x90B51000])
def test_optional_path_cleanup(path):
    words = t.payload()
    r = list(range(32)); r[4] = 0x90B50000
    pc = 0; equal = False; ctr = None; destination = None
    for _ in range(10):
        w = words[pc]; pc += 1
        if w == t.ORIGINAL:
            r[3] = path
        elif w == 0x2C030000:
            equal = r[3] == 0
        elif w == 0x40820014:
            if not equal: pc += 4
        elif w == 0x3D808026: r[12] = 0x80260000
        elif w == 0x618CC984: r[12] |= 0xC984
        elif w == 0x7D8903A6: ctr = r[12]
        elif w == 0x4E800420:
            destination = ctr; break
        elif w == 0:
            destination = t.HOOK + 4; break
        else: raise AssertionError(hex(w))
    assert destination == (t.CLEANUP if path == 0 else t.HOOK + 4)
    assert r[3] == path
    assert all(r[i] == i for i in range(32) if i not in (3, 4, 12))
    assert r[4] == 0x90B50000


def test_pal_displaced_instruction_and_cleanup():
    from ..tools.ppc import Executable
    p = Path(__file__).parents[1] / 'notes/Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not p.exists(): pytest.skip('Original PAL executable unavailable')
    e = Executable(p)
    assert e.read(t.HOOK, 8) == bytes.fromhex('806407EC80030008')
    # Original cleanup sets animation phase to zero, then returns normally.
    assert e.read(t.CLEANUP, 8) == bytes.fromhex('38000000901F068C')
