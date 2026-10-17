"""Host mutations cannot repeat the captured native entry corruption."""
import pytest

from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.native_dol import ARENA, MAGIC, SIGNATURE, plan
from .test_memory import FakeBackend


@pytest.mark.parametrize('offset,size', [(0,4),(-1,2),(31,2)])
def test_prefix_overlap_is_blocked_before_even_a_permissive_policy(offset,size):
    backend=FakeBackend()
    backend.put(SIGNATURE,MAGIC)
    memory=SonicMemory(backend,lambda *args:1)
    with pytest.raises(MemoryUnavailable,match='protected native entry'):
        memory.write_bytes_verified(ARENA+offset,bytes([1])*size,expected=bytes(size),operation='stats')
    assert backend.writes==[]
    assert memory.latest_blocked_native_write['operation']=='stats'
    assert 'test_prefix_overlap' in ''.join(memory.latest_blocked_native_write['call_stack'])


def test_following_a_relocated_entry_is_blocked_too():
    backend=FakeBackend();backend.put(SIGNATURE,MAGIC)
    memory=SonicMemory(backend,lambda *args:1)
    for hook in plan()[3]:
        with pytest.raises(MemoryUnavailable,match='protected native entry'):
            memory.write_u32(hook['target'],0xd01f1baf,expected=0,operation='permission_bits')
    assert backend.writes==[]


def test_ordinary_native_mailbox_write_remains_available():
    from ..client.native_events import SIZE
    backend=FakeBackend();backend.put(SIGNATURE,MAGIC)
    memory=SonicMemory(backend,lambda *args:1)
    address=ARENA+len(plan()[1])-SIZE+4
    memory.write_u32(address,1,expected=0,operation='stats')
    assert backend.writes==[(address,bytes.fromhex('00000001'))]
