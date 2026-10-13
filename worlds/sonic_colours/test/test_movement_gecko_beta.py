"""PAL C2 Movement BETA invariants (not live emulation assertions)."""
from ..client import movement_gate, movement_gecko
from ..client.gameplay_controls import HOOKS
from ..client.map_refresh import HOOK as MAP_HOOK


def test_movement_beta_fits_and_replaces_unwanted_hooks():
    text = movement_gecko.movement_ini()
    pairs = movement_gecko.pairs(text)
    assert len(pairs)*8 <= movement_gecko.CAPACITY_BYTES
    hooks = [0x80000000+(a&0xffffff) for a,_ in pairs if a>>24 == 0xc2]
    assert hooks.count(movement_gate.HOOK) == 1
    assert MAP_HOOK in hooks
    assert HOOKS['speed_ui'][0] in hooks
    assert HOOKS['boost_use'][0] in hooks
    assert HOOKS['boost_query'][0] in hooks


def test_both_injected_hook_variants_are_byte_encoded_correctly():
    for gecko in (False,True):
        words,deny,offset=movement_gate.payload(gecko=gecko)
        assert offset%4==0
        assert words[-1]==0
        # V6 uses a byte lookup table instead of repeated immediate masks.
        table=words[offset//4+movement_gate.DATA_WORDS:offset//4+movement_gate.DATA_WORDS+4]
        raw=b''.join(word.to_bytes(4,'big') for word in table)
        assert len(raw)==16
        for state, bit in movement_gate.STATE_PERMISSION.items():
            if bit>=8:continue # explicit wide mask, not byte lookup
            index=state-8 if state<14 else state-38+6
            assert raw[index] == 1 << bit
        states=(*range(8,14),*range(38,45))
        assert all(raw[i]==0 for i,state in enumerate(states) if state not in movement_gate.STATE_PERMISSION)
        assert words[deny]==0x71290890
        assert 0x4D820020 in words  # denied queue returns before native callbacks
        assert 0x4E800420 not in words  # never branch via CTR into a post-entry block
        if gecko:
            assert len(words)%2==0
