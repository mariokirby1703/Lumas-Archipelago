"""PowerPC restore validity, including instructions relocated into text padding."""
import struct
import pytest

from ..client.native_dol import plan


def test_generated_native_image_never_loads_its_stack_base_with_lmw():
    patches, payload, _, _ = plan()
    blobs = [payload] + [new for _, _, new in patches]
    restores = 0
    for blob in blobs:
        for (word,) in struct.iter_unpack('>I', blob):
            if word >> 26 != 46:
                continue
            first, base = word >> 21 & 31, word >> 16 & 31
            assert base < first, f'invalid lmw instruction {word:08x}'
            restores += 1
    assert restores >= 10  # Covers arena hooks and scattered event/HUD hooks.


def test_previous_control_payloads_remain_exactly_recognizable():
    from ..client.gameplay_controls import HOOKS, installed
    from ..client.memory import SonicMemory
    from ..client.native_dol import branch
    from ..world_constants import load_data
    from .test_memory import FakeBackend

    for index, (kind, row) in enumerate(load_data('gameplay_before_stack_restore.json').items()):
        backend = FakeBackend()
        base = 0x80004000 + index * 0x400
        hook = HOOKS[kind][0]
        words = list(row['words'])
        words[-1] = branch(base + len(words)*4 - 4, hook + 4)
        backend.put(base, struct.pack('>'+'I'*len(words), *words))
        backend.put(hook, branch(hook, base).to_bytes(4, 'big'))
        memory = SonicMemory(backend)
        assert installed(memory, kind) == base + row['offset']


def test_old_native_iso_is_rejected_with_repatch_instructions():
    from ..client.native_dol import ABI, MAGIC, SIGNATURE, handshake
    from ..client.memory import SonicMemory, MemoryUnavailable
    from .test_memory import FakeBackend

    backend = FakeBackend()
    backend.put(SIGNATURE, MAGIC + struct.pack('>II', ABI, 0x1778)
                + bytes.fromhex('032d23d9e9395d2fe9e53e3c9139bc0fd8c42e2cf71adc124088f78969240081')
                + bytes(16))
    with pytest.raises(MemoryUnavailable, match='repatch the original ISO'):
        handshake(SonicMemory(backend))
