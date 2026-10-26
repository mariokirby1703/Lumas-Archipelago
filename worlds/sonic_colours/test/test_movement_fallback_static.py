"""Early request gate structural tests; not Dolphin-live certification."""

from ..tools.private_assets import reference_root
from ..client import movement_gate


def test_denied_request_becomes_noop_before_callbacks():
    assert movement_gate.HOOK == 0x800395B0
    assert movement_gate.ORIGINAL == 0x9421FF40
    for gecko in (False, True):
        words, deny, offset = movement_gate.payload(gecko=gecko)
        assert words[deny] == 0x71290890
        assert 0x4D820020 in words   # reject before native queue prologue
        assert 0x901F0020 not in words  # never write to native state machine
        assert 0x4E800420 not in words # never jump via CTR to dispatcher tail
        assert movement_gate.ORIGINAL in words
        assert words[offset//4:offset//4+movement_gate.DATA_WORDS] == [0]*movement_gate.DATA_WORDS
        assert words[-1] == 0


def test_gated_native_states():
    assert set(movement_gate.STATE_PERMISSION) == {8,9,10,13,29,30,38,39,40,41,43,44,82,110}


def test_common_dispatch_is_reached_by_normal_and_forced_setters():
    from pathlib import Path
    import pytest
    from ..tools.ppc import Executable
    elf=reference_root()/'Sonic_Colours_PAL_Static_RE_v2/sonic_pal_disassembly.elf'
    if not elf.exists():pytest.skip('private executable absent')
    executable=Executable(elf)
    for site in (0x8003389c,0x80033900):
        call=list(executable.disassemble(site,4))[0]
        assert call.mnemonic=='bl' and call.op_str=='0x800395b0'
    assert int.from_bytes(executable.read(movement_gate.HOOK,4),'big')==movement_gate.ORIGINAL
    assert 0x4D820020 in movement_gate.payload(True)[0]
