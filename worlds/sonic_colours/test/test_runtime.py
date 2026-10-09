import tempfile
import pytest
from ..Items import ITEM_TABLE
from ..Locations import LOCATION_TABLE
from ..client.journal import Journal
from ..client.state import SaveGuard, Snapshot
from ..client.state import WritePolicy
from ..client.hooks import NativeHooks
from ..client.memory import MemoryUnavailable, SonicMemory
from ..client.runtime import Runtime, detect_checks, victory
from ..client.deathlink import DeathLink
from ..client.traps import TemporaryTrap
from ..client.patching import PatchManager
from . import generate
from .test_memory import FakeBackend

IDENTITY = {'seed': 'test', 'team': 0, 'slot': 1, 'revision': 'test-revision'}


def snapshot(**kwargs):
    return Snapshot(**dict({'session': 'session', 'save_identity': 'save', 'visible_slot': 1,
                           'scene': 'gameplay', 'actual_mission': 'stg120', 'stable_polls': 3,
                           'death_state': 'alive'}, **kwargs))


def test_journal_restart_dedup_and_uncertain_effect():
    with tempfile.TemporaryDirectory() as directory:
        with Journal(directory, IDENTITY) as journal:
            journal.record_history([ITEM_TABLE['Rings (+10)']])
            journal.prepare(0, ITEM_TABLE['Rings (+10)'], ['session'], 5, 15)
            journal.add_checks({123})
            with pytest.raises((OSError, BlockingIOError)):
                Journal(directory, IDENTITY)
        with Journal(directory, IDENTITY) as journal:
            assert journal.data['effects']['0']['state'] == 'prepared'
            assert journal.data['checks'] == [123]
            journal.record_history([ITEM_TABLE['Rings (+10)']])
            with pytest.raises(ValueError, match='mismatch'):
                journal.record_history([ITEM_TABLE['1-Up']])
            with pytest.raises(ValueError):
                journal.prepare(0, ITEM_TABLE['Rings (+10)'], [], 15, 25)
            journal.recover_skip(0)
        with Journal(directory, IDENTITY) as journal:
            assert journal.data['effects']['0']['state'] == 'skipped_by_operator'


def test_save_guard_never_arms_from_static_evidence():
    with tempfile.TemporaryDirectory() as directory, Journal(directory, IDENTITY) as journal:
        guard = SaveGuard(journal)
        with pytest.raises(MemoryUnavailable, match='new_game_indicator_unverified'):
            guard.arm(snapshot(), operator_confirmed=True, fresh_evidence={'clears': True, 'rings': True})
        for value in (snapshot(), snapshot(visible_slot=2), snapshot(session='old'), snapshot(save_identity='other')):
            with pytest.raises(MemoryUnavailable): guard.check(value)
        assert journal.data['save_identity'] is None
        memory = SonicMemory(FakeBackend())
        memory.verify_revision = lambda: 'test-revision'
        state = NativeHooks().snapshot(memory)
        assert state.scene == 'unclassified' and not state.progress_verified


def test_persisted_ring_modes_and_goal_never_from_inventory():
    for mode in ('singles', 'per_level'):
        data = generate({'red_ring_checks': mode}).worlds[1].fill_slot_data()
        partial = snapshot(persisted_rings={'stg120': frozenset({1, 3})})
        complete = snapshot(persisted_rings={'stg120': frozenset(range(1, 6))})
        name = 'Tropical Resort Act 3'
        if mode == 'singles':
            assert detect_checks(data, partial) == {LOCATION_TABLE[f'{name} - Red Ring {i}'].code for i in (1, 3)}
            assert len(detect_checks(data, complete)) == 5
        else:
            assert not detect_checks(data, partial)
            assert detect_checks(data, complete) == {LOCATION_TABLE[name + ' - All 5 Red Rings'].code}
        assert not victory(data, snapshot())
        assert victory(data, snapshot(persisted_clears=frozenset({'stg790'})))


@pytest.mark.parametrize('mode', ['singles', 'per_level'])
def test_pickups_lost_before_save_are_never_credited(mode):
    data = generate({'red_ring_checks': mode, 'goal': 'all_red_rings'}).worlds[1].fill_slot_data()
    rings = frozenset(range(1, 6))
    picked_up = snapshot(active_rings={'stg120': rings})
    assert not detect_checks(data, picked_up)
    assert not victory(data, picked_up)
    assert not detect_checks(data, snapshot())  # death/exit before save
    committed = snapshot(persisted_rings={'stg120': rings})
    assert len(detect_checks(data, committed)) == (5 if mode == 'singles' else 1)


@pytest.mark.parametrize('quality,expected', [(0, 4), (1, 3), (2, 2), (3, 1), (4, 0)])
def test_rank_threshold_comparison(quality, expected):
    locations = {name: data.code for name, data in LOCATION_TABLE.items() if data.kind == 'rank' and data.mission == 'stg120'}
    data = {'locations': locations}
    assert len(detect_checks(data, snapshot(awarded_ranks={'stg120': quality}))) == expected
    assert not detect_checks(data, snapshot())


def test_deathlink_one_event_remote_no_echo_and_expiration():
    with tempfile.TemporaryDirectory() as directory, Journal(directory, IDENTITY) as journal:
        death = DeathLink(journal)
        def poll(state, now=0, safe=True, kill=lambda: None):
            return death.poll(safe=safe, native_state=state, now=now, kill=kill)
        for _ in range(3): assert not poll('alive')
        assert poll('dying')
        assert not poll('dead')
        assert not poll('respawning')
        for _ in range(3): assert not poll('alive')
        event = {'time': 1, 'source': 'Friend', 'cause': 'test'}
        assert death.receive(event, 0)
        assert not death.receive(event, 0)
        calls = []
        assert not poll('alive', kill=lambda: calls.append('kill'))
        assert calls == ['kill']
        death = DeathLink(journal)  # Reconnect before remote death becomes visible.
        for _ in range(10):
            assert not poll('alive')
        assert death.remote_cycle
        assert not poll('dying')
        assert not poll('dead')
        assert not poll('respawning')
        for _ in range(3): assert not poll('alive')
        assert death.state == 'ALIVE'
        assert death.receive({'time': 2, 'source': 'Friend'}, 0)
        assert not poll('alive', now=31, kill=lambda: calls.append('kill'))
        assert calls == ['kill']


def test_temporary_trap_pause_restore_failure_and_patch_refusal():
    calls = []
    trap = TemporaryTrap()
    trap.start('stage1', 5, lambda: calls.append('apply'), lambda ctx: calls.append(('restore', ctx)))
    trap.tick('stage1', 100, False)
    assert trap.remaining == 5
    trap.tick('stage1', 5, True)
    assert calls == ['apply', ('restore', 'stage1')]
    def failed_restore(ctx): raise MemoryUnavailable('emulator closed')
    trap.start('stage2', 5, lambda: None, failed_restore)
    with pytest.raises(MemoryUnavailable): trap.tick('stage3', 1, True)
    assert trap.context == 'stage2'
    with pytest.raises(MemoryUnavailable): trap.start('stage3', 5, lambda: None, lambda ctx: None)
    backend = FakeBackend()
    with pytest.raises(MemoryUnavailable, match='JIT'):
        PatchManager().install(SonicMemory(backend), 0x80004000, b'1234', b'5678')
    assert not backend.writes


def test_unverified_runtime_queues_without_writes_or_checks():
    data = generate().worlds[1].fill_slot_data()
    with tempfile.TemporaryDirectory() as directory, Journal(directory, IDENTITY) as journal:
        runtime = Runtime(data, journal, SaveGuard(journal), NativeHooks())
        backend = FakeBackend()
        memory = SonicMemory(backend)
        memory.verify_revision = lambda: 'test-revision'
        checks, goal = runtime.poll(memory, [ITEM_TABLE['Rings (+10)']], True)
        assert not checks and not goal
        assert runtime.pending_effects() == [0]
        assert not journal.data['checks'] and not backend.writes


def test_write_policy_rejects_all_unverified_capabilities():
    with tempfile.TemporaryDirectory() as directory, Journal(directory, IDENTITY) as journal:
        backend = FakeBackend()
        memory = SonicMemory(backend)
        policy = WritePolicy(memory, SaveGuard(journal), lambda memory: snapshot())
        for operation in ('progress_c', 'wisp_permissions', 'unknown'):
            with pytest.raises(MemoryUnavailable, match='requires_verified_hook'):
                policy(operation, 0x90001000, 4)
        with pytest.raises(MemoryUnavailable, match='wrong_game'):
            policy('stats', 0x90001000, 4)
        assert not backend.writes


def test_receipt_effect_exactly_once_with_injected_verified_test_adapter():
    class TestGuard:
        def check(self, value): return ['test-session']
        def check_stats(self, value): return ['test-session']
    class TestHooks:
        def require(self, capability): pass
    data = generate().worlds[1].fill_slot_data()
    with tempfile.TemporaryDirectory() as directory, Journal(directory, IDENTITY) as journal:
        runtime = Runtime(data, journal, TestGuard(), TestHooks())
        backend = FakeBackend()
        backend.put(0x90001000, (5).to_bytes(4, 'big'))
        memory = SonicMemory(backend, lambda *args: 'test-session')
        runtime.snapshot = snapshot(rings_address=0x90001000)
        items = [ITEM_TABLE['Rings (+10)']]
        journal.record_history(items)
        runtime.apply_effects(memory, items)
        assert memory.read_u32(0x90001000) == 15
        runtime.apply_effects(memory, items)
        assert len(backend.writes) == 1
        assert not runtime.pending_effects()
        next_items = items + [ITEM_TABLE['Rings (+25)']]
        journal.record_history(next_items)
        backend.corrupt = True
        with pytest.raises(MemoryUnavailable, match='readback_mismatch'):
            runtime.apply_effects(memory, next_items)
        assert journal.data['effects']['1']['state'] == 'prepared'
        writes = len(backend.writes)
        with pytest.raises(MemoryUnavailable, match='WRITE_UNCERTAIN'):
            runtime.apply_effects(memory, next_items)
        assert len(backend.writes) == writes
