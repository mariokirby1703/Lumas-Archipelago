import pytest
from ..client import speed_initial as s
from ..client.memory import MemoryUnavailable


def test_original_reset_stores_default_speed_directly():
    from pathlib import Path
    from ..tools.ppc import Executable
    path=Path(__file__).parents[1]/'notes/Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not path.exists():pytest.skip('Original PAL executable absent')
    e=Executable(path)
    assert e.read(s.ADDRESS,4)==s.ORIGINAL.to_bytes(4,'big')
    assert e.read(0x8026FE9C,4)==bytes.fromhex('90030004')
    # No intervening instruction writes r0 before its store.
    for x in e.disassemble(s.ADDRESS+4,0x18):
        assert not x.op_str.startswith('r0,')
    assert s.PATCHED==0x38000000


def test_exact_initial_speed_normalization_and_profile_capacity():
    original=s.ORIGINAL.to_bytes(4,'big')
    assert s.normalize(original,s.ADDRESS)==original
    assert s.normalize(s.PATCHED.to_bytes(4,'big'),s.ADDRESS)==original
    with pytest.raises(MemoryUnavailable):s.normalize(bytes(4),s.ADDRESS)
    from ..client.movement_gecko import movement_ini,pairs,CAPACITY_BYTES
    codes=pairs(movement_ini())
    assert (0x0426FE80,s.PATCHED) in codes
    assert len(codes)*8<=CAPACITY_BYTES
