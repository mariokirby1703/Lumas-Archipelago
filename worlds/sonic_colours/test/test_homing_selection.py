"""The removed Double Jump fallback must not intercept native Homing selection."""
from ..client.native_dol import Dol,plan,patch_dol
HOOK=0x800977D0
ORIGINAL=0x2C03FFFF
from ..client.movement_gate import STATE_PERMISSION
from ..tools.private_assets import reference_root


def test_homing_selector_remains_original_in_patched_iso():
    raw=(reference_root()/'memdumps_and_more/main.dol').read_bytes()
    assert Dol(raw).read(HOOK,4)==ORIGINAL.to_bytes(4,'big')
    assert not any(a<=HOOK<a+len(new) for a,old,new in plan()[0])
    patched=patch_dol(raw,bytes(32))
    image=patched[0] if isinstance(patched,tuple) else patched
    assert Dol(image).read(HOOK,4)==ORIGINAL.to_bytes(4,'big')


def test_homing_and_double_jump_unlocks_remain_independent():
    assert STATE_PERMISSION[13]==2
    assert STATE_PERMISSION[8]==0
