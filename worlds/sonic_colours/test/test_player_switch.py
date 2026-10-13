import pytest
from ..client import player_switch as p
from ..client.memory import MemoryUnavailable


def test_pressed_and_unpressed_switch_use_original_neutral_return():
    assert p.ADDRESS+(p.ORIGINAL&0xfffc)==0x802F187C
    assert p.ADDRESS+(p.DISABLED&0x3fffffc)==0x802F187C
    assert p.DISABLED>>26==18 and not p.DISABLED&1
    # Unconditional, non-linking branch: both predicate results skip all
    # transfer messages/effects and the request-114 path.
    for pressed in (False,True):
        assert p.ADDRESS+(p.DISABLED&0x3fffffc)>0x802F1860


def test_exact_original_recovery_and_unknown_code_rejection():
    old=p.ORIGINAL.to_bytes(4,'big');new=p.DISABLED.to_bytes(4,'big')
    assert p.normalize(old,p.ADDRESS)==old
    assert p.normalize(new,p.ADDRESS)==old
    with pytest.raises(MemoryUnavailable):p.normalize(bytes(4),p.ADDRESS)


def test_assist_item_and_stomp_ids():
    from ..Items import ITEM_TABLE,MOVEMENT_POOL,classification
    from ..world_constants import BASE_ID
    from BaseClasses import ItemClassification
    assert ITEM_TABLE['Stomp']==BASE_ID+41
    assert 'Ground Pound' not in ITEM_TABLE
    assert ITEM_TABLE['Assist Change']==BASE_ID+47
    assert MOVEMENT_POOL.count('Assist Change')==1
    assert classification('Assist Change')==ItemClassification.progression


@pytest.mark.parametrize('pressed',[0,1])
@pytest.mark.parametrize('allowed',[0,1])
def test_native_assist_predicate_before_transfer(pressed,allowed):
    from capstone import Cs,CS_ARCH_PPC,CS_MODE_32,CS_MODE_BIG_ENDIAN
    words,offset=p.payload()
    ops=list(Cs(CS_ARCH_PPC,CS_MODE_32|CS_MODE_BIG_ENDIAN).disasm(b''.join(x.to_bytes(4,'big') for x in words[:8]),0x80002000))
    assert [x.mnemonic for x in ops]==['mflr','bl','mflr','lwz','and','mtlr','cmpwi','b']
    assert ops[3].op_str=='r12, 0x18(r12)'
    assert ops[4].op_str=='r3, r3, r12'
    assert 8+0x18==offset
    assert bool(pressed & allowed)==bool(pressed and allowed)
    assert p.HOOK+4==p.ADDRESS


@pytest.mark.parametrize('allowed',[0,1])
def test_assist_configuration_guarded_data_only(monkeypatch,allowed):
    from collections import Counter
    class Memory:
        def read_u32(self,a):return 1-allowed
        def write_u32(self,a,v,**kw):
            assert a==0x80002a00 and v==allowed
            assert kw=={'expected':1-allowed,'operation':'assist_change'}
    monkeypatch.setattr(p,'installed_data',lambda m:0x80002a00)
    assert p.configure(Memory(),None,{'counts':Counter({'Assist Change':allowed})})['allowed']==bool(allowed)
