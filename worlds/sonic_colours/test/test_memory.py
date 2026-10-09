import struct
import pytest
from ..client.memory import SonicMemory, MemoryUnavailable, valid_range
from ..client.versions import VERSION, verify_revision


class FakeBackend:
    def __init__(self):
        self.data = {}
        self.writes = []
        self.corrupt = False

    def put(self, address, data):
        self.data.update((address + i, b) for i, b in enumerate(data))

    def read_bytes(self, address, size):
        return bytes(self.data.get(address + i, 0) for i in range(size))

    def write_bytes(self, address, data):
        self.writes.append((address, data))
        self.put(address, b'\xff' * len(data) if self.corrupt else data)


def test_be_reads_writes_masks_and_denied_default():
    backend = FakeBackend()
    memory = SonicMemory(backend)
    address = 0x90001000
    backend.put(address, bytes.fromhex('12345678'))
    assert memory.read_u8(address) == 0x12
    assert memory.read_u16(address) == 0x1234
    assert memory.read_u32(address) == 0x12345678
    with pytest.raises(MemoryUnavailable, match='no verified write policy'):
        memory.write_u32(address, 0, expected=0x12345678, operation='stats')
    assert not backend.writes
    memory.write_guard = lambda *args: 'verified-test-context'
    memory.read_modify_write_masked_u32(address, 0xff, 0xaa, operation='stats')
    assert memory.read_u32(address) == 0x123456aa
    memory.write_f32(address, 1.25, expected=memory.read_f32(address), operation='stats')
    assert backend.read_bytes(address, 4) == struct.pack('>f', 1.25)
    assert memory.read_f32(address) == 1.25


@pytest.mark.parametrize('address,size', [(0, 4), (0x817ffffe, 4), (0x93ffffff, 2),
    (0x80000000, 0), (0x94000000, 1), (0xffffffff, 4), (0x90000000, -1)])
def test_ranges(address, size):
    assert not valid_range(address, size)
    with pytest.raises(MemoryUnavailable):
        SonicMemory(FakeBackend()).read_bytes(address, size)


def test_pointer_chain_inline_flags_and_bits():
    backend = FakeBackend()
    memory = SonicMemory(backend, lambda *args: 1)
    def word(a, v): backend.put(a, v.to_bytes(4, 'big'))
    word(VERSION['manager_global_candidate'], 0x90000100)
    word(0x90000130, 0x90001000)
    backend.put(0x90001000, b'\x01')
    selected = 0x90001000 + 8 + 0x19608
    flags = selected + 0x1c
    assert memory.resolve_flags_ptr() == (0x90000100, 0x90001000, 1, selected, flags)
    memory.write_progress_bit(flags, 150, True)
    assert memory.read_progress_bit(flags, 150)
    assert not memory.read_progress_bit(flags, 149)
    memory.write_progress_bit(flags, 150, False)
    assert not memory.read_progress_bit(flags, 150)
    word(VERSION['manager_global_candidate'], 0)
    with pytest.raises(MemoryUnavailable, match='invalid_pointer'):
        memory.resolve_flags_ptr()


def test_compare_context_race_and_failed_readback():
    backend = FakeBackend()
    memory = SonicMemory(backend, lambda *args: 1)
    with pytest.raises(MemoryUnavailable, match='compare_failed'):
        memory.write_u32(0x90001000, 2, expected=1, operation='stats')
    assert not backend.writes
    tokens = iter([1, 2])
    memory.write_guard = lambda *args: next(tokens)
    with pytest.raises(MemoryUnavailable, match='context_changed'):
        memory.write_u32(0x90001000, 2, expected=0, operation='stats')
    assert not backend.writes
    memory.write_guard = lambda *args: 1
    backend.corrupt = True
    with pytest.raises(MemoryUnavailable, match='readback_mismatch'):
        memory.write_u32(0x90001000, 2, expected=0, operation='stats')


def test_partial_read_and_revision_rejection():
    backend = FakeBackend()
    memory = SonicMemory(backend)
    with pytest.raises(MemoryUnavailable, match='wrong_game'):
        verify_revision(memory)
    backend.put(0x80000000, b'SNCP8P')
    backend.put(0x80000007, b'\x01')
    with pytest.raises(MemoryUnavailable, match='unknown_revision'):
        verify_revision(memory)
    backend.put(0x80000007, b'\0')
    with pytest.raises(MemoryUnavailable, match='SHA256'):
        verify_revision(memory)
    backend.read_bytes = lambda a, s: b''
    with pytest.raises(MemoryUnavailable, match='partial_read'):
        memory.read_u32(0x90001000)
