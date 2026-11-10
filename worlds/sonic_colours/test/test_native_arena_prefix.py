"""Reproduce the exact entry-word damage captured in the Game Land crashes."""
from .dol_memory import read_dol_memory

import hashlib
import pytest

from ..client.native_dol import ARENA, ARENA_PREFIX_SIZE, Dol, patch_dol, plan
from ..client.memory import SonicMemory, MemoryUnavailable
from .test_seed_patch import original_dol


def test_captured_low_memory_write_no_longer_replaces_a_stack_prologue():
    original = original_dol()
    patched, _ = patch_dol(original, 'ArenaRegression')
    image = Dol(patched)
    _, payload, _, hooks = plan()
    assert payload[:ARENA_PREFIX_SIZE] == bytes(ARENA_PREFIX_SIZE)
    assert min(h['target'] for h in hooks) == ARENA + ARENA_PREFIX_SIZE

    class Backend:
        def read_bytes(self, address, size):
            if address == 0x80000000:
                return (b'SNCP8P'+bytes(2))[:size]
            if address == 0x80000007:
                return bytes(1)
            return read_dol_memory(image, address, size)

    memory = SonicMemory(Backend())
    memory.required_native_seed = 'ArenaRegression'
    # The last two real captures contained these values at 80001800.
    previous = bytes(4)
    for word in (0xd01f1baf, 0xd01f03af):
        damaged = word.to_bytes(4, 'big')
        image.replace(ARENA, previous, damaged)
        assert memory.verify_revision() == hashlib.sha256(original).hexdigest()
        for hook in hooks:
            offset = hook['target'] - ARENA
            assert image.read(hook['target'], 4) == payload[offset:offset+4]
        previous = damaged

    # Dolphin installs this marker with cheats disabled, before gameplay.
    image.replace(ARENA+4, bytes(8), b'STUBHAXX')
    assert memory.verify_revision() == hashlib.sha256(original).hexdigest()
    image.replace(ARENA+12, bytes(4), bytes.fromhex('01000000'))
    with pytest.raises(MemoryUnavailable, match='prefix modification'):
        memory.verify_revision()
    image.replace(ARENA+12, bytes.fromhex('01000000'), bytes(4))
    image.replace(ARENA+4, b'STUBHAXX', b'STUBHAXY')
    with pytest.raises(MemoryUnavailable, match='prefix modification'):
        memory.verify_revision()
    image.replace(ARENA+4, b'STUBHAXY', bytes(8))

    image.replace(ARENA+4, bytes(4), bytes.fromhex('01000000'))
    with pytest.raises(MemoryUnavailable, match='prefix modification') as failure:
        memory.verify_revision()
    message = str(failure.value)
    assert 'prefix_address=0x80001800' in message
    assert 'observed=' + previous.hex() + '01000000' + bytes(24).hex() in message
    assert 'expected=' + bytes(32).hex() in message
    assert 'changed_addresses=0x80001804;' in message
    assert 'executable_entries_match=True' in message
    image.replace(ARENA+4, bytes.fromhex('01000000'), bytes(4))

    # Damage to actual code must still block writes, even with a valid header.
    target = hooks[0]['target']
    image.replace(target, image.read(target, 4), (0xd01f1baf).to_bytes(4, 'big'))
    with pytest.raises(MemoryUnavailable, match='executable entry modified'):
        memory.verify_revision()
