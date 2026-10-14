import pytest
from ..client.ap_hud_mailbox import encode,publication_writes,acknowledged,SIZE


def test_atomic_order_and_two_terminated_lines():
    data=encode(2,'Sent Test Item','to SM64 Player')
    assert len(data)==SIZE
    writes=publication_writes(2,'Sent Test Item','to SM64 Player')
    assert writes[0]==(0,b'\0\0\0\1')
    assert writes[1]==(4,data[4:]) and writes[2]==(0,data[:4])
    assert data[4:132].split(b'\0')[0]==b'Sent Test Item'
    assert data[132:].split(b'\0')[0]==b'to SM64 Player'


@pytest.mark.parametrize('generation',[0,1,3,-2,0x100000000,True])
def test_invalid_generation(generation):
    with pytest.raises(ValueError):encode(generation,'a','b')


def test_no_silent_buffer_truncation_or_partial_ack():
    with pytest.raises(ValueError):encode(2,'a'*128,'b')
    assert acknowledged(2,2,2,2)
    assert not acknowledged(2,1,2,2)
    assert not acknowledged(2,2,4,2)
    assert not acknowledged(2,2,2,0)
