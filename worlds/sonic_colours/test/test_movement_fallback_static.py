"""Early request gate structural tests; not Dolphin-live certification."""
from ..client import movement_gate, movement_gecko


def test_denied_request_becomes_noop_before_callbacks():
    assert movement_gate.HOOK == 0x8003388C
    assert movement_gate.ORIGINAL == 0x80030020
    for gecko in (False, True):
        words, deny, offset = movement_gate.payload(gecko=gecko)
        assert words[deny] == 0x71290090
        assert 0x809F0020 in words   # load previous pending request into r4
        assert 0x901F0020 not in words  # never write to native state machine
        assert 0x4E800420 not in words # never jump via CTR to dispatcher tail
        assert movement_gate.ORIGINAL in words
        assert words[offset//4:offset//4+movement_gate.DATA_WORDS] == [0]*movement_gate.DATA_WORDS
        assert words[-1] == 0


def test_gated_native_states_and_capacity():
    assert set(movement_gate.STATE_PERMISSION) == {8,9,13,29,30,38,39,40,41,43,44}
    text=movement_gecko.movement_ini()
    assert len(movement_gecko.pairs(text))*8 <= movement_gecko.CAPACITY_BYTES
