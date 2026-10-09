"""Production accessors over original PAL captures; no guest CPU execution."""
import struct
import pytest
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.hooks import NativeHooks
from ..client.state import SaveGuard, WritePolicy, PlaythroughState
from ..client.journal import Journal
from ..client.runtime import Runtime, inventory
from ..client.capsule_refresh import HOOK, ORIGINAL, payload_words
from ..client import native_read
from .test_native_originals import PAIRS
from .test_pickup_integration import Overlay
from .test_runtime import IDENTITY
from . import generate

pytestmark = pytest.mark.skipif(not PAIRS, reason='private original captures absent')


def hook(backend):
    target = 0x80001800
    words = payload_words()
    words[-1] = 0x48000000 | ((HOOK + 4 - (target + len(words)*4 - 4)) & 0x3fffffc)
    backend.write_bytes(target, struct.pack('>' + 'I'*len(words), *words))
    backend.write_bytes(HOOK, (0x48000000 | ((target-HOOK) & 0x3fffffc)).to_bytes(4, 'big'))


@pytest.mark.parametrize('patch', ['absent', 'valid', 'invalid'])
def test_optional_hook_core_identity_and_safe_writes(tmp_path, patch):
    b = Overlay(PAIRS[0]); m = SonicMemory(b)
    if patch == 'valid':
        hook(b)
    elif patch == 'invalid':
        b.write_bytes(HOOK, b'\x60\0\0\0')
    with Journal(tmp_path, IDENTITY) as j:
        h = NativeHooks(j); g = SaveGuard(j)
        s = h.snapshot(m); g.observe(s)
        assert s.actual_mission == 'stg110' and s.scene == 'gameplay'
        if patch == 'invalid':
            assert not s.pickup_verified and not s.scene_verified
            assert not j.data.get('bootstrap')
            assert 'observed 0x60000000' in s.status
            m.write_guard = WritePolicy(m, g, h.snapshot)
            before = len(b.writes)
            with pytest.raises(MemoryUnavailable):
                m.write_u32(0x90001000, 1, expected=0, operation='stats')
            assert len(b.writes) == before
        else:
            assert s.new_game_verified and g.can_record_pickups(s)


def test_zero_disc_and_rejected_frame_recover_same_intro(tmp_path, monkeypatch):
    b = Overlay(PAIRS[0]); m = SonicMemory(b)
    with Journal(tmp_path, IDENTITY) as j:
        h = NativeHooks(j); g = SaveGuard(j)
        s = h.snapshot(m); g.observe(s)
        epoch = s.stage_epoch; bootstrap = dict(j.data['bootstrap'])
        real_read = b.read_bytes
        remaining = [3]
        def zero_header(address, size):
            if address == 0x80000000 and size == 6 and remaining[0]:
                remaining[0] -= 1
                return bytes(size)
            return real_read(address, size)
        b.read_bytes = zero_header
        with pytest.raises(MemoryUnavailable, match='wrong_game'):
            h.snapshot(m)
        g.suspend()
        assert g.state == PlaythroughState.MANDATORY_PROLOGUE
        s = h.snapshot(m); g.observe(s)
        assert s.stage_epoch == epoch and j.data['bootstrap'] == bootstrap
        original = native_read._read_stage_objects
        attempts = [0]
        def changing(memory):
            attempts[0] += 1
            if attempts[0] <= 3:
                raise MemoryUnavailable('stage_context_changed')
            return original(memory)
        monkeypatch.setattr(native_read, '_read_stage_objects', changing)
        with pytest.raises(MemoryUnavailable, match='stage_context_changed'):
            h.snapshot(m)
        assert attempts[0] == 3
        g.suspend(); s = h.snapshot(m); g.observe(s)
        assert s.stage_epoch == epoch and g.can_record_pickups(s)
        g.disarm(); g.observe(s)
        assert g.state == PlaythroughState.MANDATORY_PROLOGUE
        for _ in range(4):
            assert not h.reject_observation({'disc_id_hex': '000000000000'}, 'wrong_game: zero')
        assert h.stage_key is not None
        other = {'disc_id_hex': '524d43503031'}
        assert not h.reject_observation(other, 'wrong_game: other game')
        assert not h.reject_observation(other, 'wrong_game: other game')
        assert h.reject_observation(other, 'wrong_game: other game')
        assert h.stage_key is None


@pytest.mark.parametrize('accessor', ['read_capsules', 'read_actors'])
def test_optional_capsule_failure_keeps_essential_frame(tmp_path, monkeypatch, accessor):
    b = Overlay(PAIRS[0]); m = SonicMemory(b)
    def fail(*args):
        raise MemoryUnavailable('capsule_context_changed')
    monkeypatch.setattr(native_read, accessor, fail)
    s = NativeHooks().snapshot(m)
    assert s.scene_verified and s.pickup_verified
    assert bool(s.rings_address) == (accessor == 'read_capsules')
    assert s.actual_mission == 'stg110'
    field = 'capsule_error' if accessor == 'read_capsules' else 'player_error'
    assert s.evidence['native_data']['stage_objects'][0][field] == 'capsule_context_changed'


def test_optional_zero_hook_read_does_not_override_original_text_proof(tmp_path, monkeypatch):
    b = Overlay(PAIRS[0]); m = SonicMemory(b)
    original = m.read_u32
    monkeypatch.setattr(m, 'read_u32', lambda address: 0 if address == HOOK else original(address))
    with Journal(tmp_path, IDENTITY) as j:
        h = NativeHooks(j); g = SaveGuard(j)
        for _ in range(3):
            s = h.snapshot(m); g.observe(s)
        assert m.revision_observation['verified'] and g.can_record_pickups(s)
        m.write_guard = WritePolicy(m, g, h.snapshot)
        from ..Items import ITEM_TABLE
        h.project_live_permissions(m, s, inventory([ITEM_TABLE['Cyan Laser Wisp']]),
                                   generate().worlds[1].fill_slot_data())
        assert not h.capsule_refresh_status['available']
        assert 'observed 0x00000000' in h.capsule_refresh_status['reason']
        stage = s.evidence['native_data']['stage_objects'][0]
        assert m.read_u8(stage['actor_state']+0x90) == 2


@pytest.mark.parametrize('patch', ['absent', 'valid'])
def test_intro_working_record_and_cyan_permissions_without_persistent_writes(tmp_path, patch):
    b = Overlay(PAIRS[0]); m = SonicMemory(b)
    manager, container, _, selected = m.resolve_selected_slot()
    b.write_bytes(container + 8 + 3*0x19608, m.read_bytes(selected, 0x19608))
    b.write_bytes(container, b'\x03')
    if patch == 'valid':
        hook(b)
    with Journal(tmp_path, IDENTITY) as j:
        h = NativeHooks(j); g = SaveGuard(j)
        r = Runtime(generate().worlds[1].fill_slot_data(), j, g, h)
        m.write_guard = WritePolicy(m, g, h.snapshot)
        for _ in range(3):
            r.poll(m, [], False)
        assert r.snapshot.new_game_verified and g.can_record_pickups(r.snapshot)
        assert r.snapshot.evidence['internal_selected_index'] == 3
        assert j.data['save_identity'] is None
        with pytest.raises(MemoryUnavailable, match='unknown_selected_slot'):
            m.resolve_flags_ptr()
        from ..Items import ITEM_TABLE
        owned = inventory([ITEM_TABLE['Cyan Laser Wisp']])
        r.project_permissions(m, owned)
        assert h.capsule_refresh_status['available'] == (patch == 'valid')
        stage = r.snapshot.evidence['native_data']['stage_objects'][0]
        assert m.read_u8(stage['stage']+0x61) == 2
        assert m.read_u8(stage['actor_state']+0x90) == 2
