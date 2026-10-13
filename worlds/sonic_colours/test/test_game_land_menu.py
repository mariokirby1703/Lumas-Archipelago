import pytest
from ..client import game_land_menu as g
from ..client.memory import MemoryUnavailable


def test_patch_targets_preserve_native_unlock_and_visual_routes():
    address=0x802F0D98
    def target(word):
        displacement=word&0x3fffffc
        if displacement&0x2000000:displacement-=0x4000000
        return address+displacement
    assert target(g.PATCHES[address][0])==0x8015EFCC
    assert target(g.PATCHES[address][1])==0x8015EE9C
    assert g.PATCHES[0x802ED70C][1]==0x3B000000
    assert g.PATCHES[0x802ED79C][1]==0x38160000
    assert g.PATCHES[0x802EDA78][1]==0x8077012C


def test_original_reconstruction_rejects_partial_or_unknown_patch():
    base=min(g.PATCHES);raw=bytearray(max(g.PATCHES)-base+4)
    for address,(old,new) in g.PATCHES.items():raw[address-base:address-base+4]=old.to_bytes(4,'big')
    original=bytes(raw)
    assert g.normalize(None,original,base)==original
    for address,(old,new) in g.PATCHES.items():raw[address-base:address-base+4]=new.to_bytes(4,'big')
    assert g.normalize(None,bytes(raw),base)==original
    raw[0:4]=g.PATCHES[base][0].to_bytes(4,'big')
    with pytest.raises(MemoryUnavailable,match='partially'):g.normalize(None,bytes(raw),base)
    raw[0:4]=bytes(4)
    with pytest.raises(MemoryUnavailable,match='unknown_revision'):g.normalize(None,bytes(raw),base)
