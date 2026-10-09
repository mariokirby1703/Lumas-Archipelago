"""Optional original-capture regression tests. No invented RAM fixtures.

The private captures are deliberately excluded from Git/APWorld packages.
These tests verify native reads, never a live writer or in-game patch.
"""
from pathlib import Path

import pytest

from ..client.hooks import NativeHooks
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.native_read import read_stage_objects, read_saved_progress
from ..tools.read_dumps import DumpBackend
from ..world_constants import load_data


ROOT = Path(__file__).parents[1] / 'notes/memdumps_and_more'
PAIRS = [(a, b) for directory in sorted(ROOT.glob('Sonic_Colours_RAM_Dumps_Part*'))
         for a, b in zip(sorted(directory.glob('mem1*.raw')), sorted(directory.glob('mem2*.raw')))]


@pytest.mark.skipif(not PAIRS, reason='private original RAM captures not installed')
@pytest.mark.parametrize('first,second', PAIRS, ids=[a.stem for a, _ in PAIRS])
def test_production_reader_on_original_capture(first, second):
    memory = SonicMemory(DumpBackend(first, second))
    state = NativeHooks().snapshot(memory)  # Includes the REAL text SHA check.
    native = state.evidence['native_data']
    assert not any(key.endswith('_error') for key in native), native
    assert len(native['saved_progress']['rank_records']) == 66
    assert len(native['saved_progress']['physical_red_rings']) == 36
    assert not state.save_identity_verified and state.save_identity is None
    if '200443' in first.name:
        assert state.new_game_verified and state.fresh_fields == (True, True)
        assert state.actual_mission == 'stg110' and state.scene == 'gameplay'
        assert state.active_rings['stg110'] == frozenset({1})
        assert native['stage_objects'][0]['player']['rings'] == 16
    if '201102' in first.name:
        assert state.scene == 'results' and not state.new_game_verified
        assert native['stage_objects'][0]['current_red_ring_mask'] == 17
        assert state.active_rings['stg110'] == frozenset({1, 5})
        # Result UI is not the live player's ring/score fields.
        assert not state.persisted_rings['stg110']
    if '202546' in first.name:
        assert state.persisted_rings['stg110'] == frozenset({1, 5})
        assert state.awarded_ranks['stg110'] == 2
        assert native['saved_progress']['rank_records']['stg110'] == {
            'raw_rank': 2, 'score': 705200, 'time_raw': 12019, 'record_index': 0}
    if '210538' in first.name:
        assert state.actual_mission == 'stgD10' and state.scene == 'gameplay'
        assert native['stage_objects'][0]['player']['mode'] == 2
        assert native['stage_objects'][0]['player']['rings'] == 5
    if '212125' in first.name:
        assert native['stage_objects'][0]['player']['held_wisp'] == 1
        assert native['stage_objects'][0]['player']['boost'] == pytest.approx(60.6)
    if '212954' in first.name:
        assert state.scene == 'dying' and state.death_state == 'dying'
        assert native['stage_objects'][0]['death_count'] == 1
    if '213123' in first.name:
        assert state.scene == 'gameplay'
        assert native['stage_objects'][0]['death_count'] == 1
    if '213540' in first.name:
        assert state.persisted_rings['stg120'] == frozenset({2})
    with pytest.raises(MemoryUnavailable, match='original_dump_is_read_only'):
        memory.backend.write_bytes(0x80000000, b'x')


@pytest.mark.skipif(not PAIRS, reason='private original RAM captures not installed')
@pytest.mark.parametrize('corruption,reader,reason', [
    (0x808F336C, read_stage_objects, 'invalid_pointer'),
    (0x808F34F8, lambda m: read_saved_progress(m, load_data('progress_bits.json')), 'invalid_pointer'),
])
def test_corrupt_original_root_is_rejected(corruption, reader, reason):
    original = DumpBackend(*PAIRS[0])
    class Corrupt:
        def read_bytes(self, address, size):
            return bytes(size) if address == corruption else original.read_bytes(address, size)
    with pytest.raises(MemoryUnavailable, match=reason):
        reader(SonicMemory(Corrupt()))


@pytest.mark.skipif(not PAIRS, reason='private original RAM captures not installed')
def test_clear_trace_does_not_credit_checks_when_coherent_accessor_fails():
    first, second = next(pair for pair in PAIRS if '202546' in pair[0].name)
    original = DumpBackend(first, second)
    class Corrupt:
        def read_bytes(self, address, size):
            return bytes(size) if address == 0x808F34F8 else original.read_bytes(address, size)
    state = NativeHooks().snapshot(SonicMemory(Corrupt()))
    assert state.candidate_clears == frozenset({'stg110'})
    assert not state.progress_verified and not state.persisted_clears
    assert not state.persisted_rings and not state.awarded_ranks


@pytest.mark.skipif(not PAIRS, reason='private original RAM captures not installed')
def test_original_unsaved_intro_pickup_is_not_durably_credited(tmp_path):
    from ..client.journal import Journal
    from ..client.runtime import Runtime
    from ..client.state import SaveGuard
    from ..Locations import LOCATION_TABLE
    from . import generate
    memory = SonicMemory(DumpBackend(*PAIRS[0]))
    slot = generate().worlds[1].fill_slot_data()
    identity = {'seed': slot['seed_name'], 'team': 0, 'slot': 1, 'revision': memory.verify_revision()}
    with Journal(tmp_path, identity) as journal:
        guard = SaveGuard(journal)
        guard.confirm_new_game()
        runtime = Runtime(slot, journal, guard, NativeHooks())
        for _ in range(3):
            checks, goal = runtime.poll(memory, [], True)
            assert not checks and not goal and not guard.armed
        assert runtime.snapshot.active_rings['stg110'] == frozenset({1})
        assert journal.data['bootstrap']['checks'] == []
        assert journal.data['save_identity'] is None
        assert journal.data['effects'] == {}


@pytest.mark.skipif(not PAIRS, reason='private original RAM captures not installed')
def test_original_capture_session_invalidation_and_client_restart():
    memory = SonicMemory(DumpBackend(*PAIRS[0]))
    hooks = NativeHooks()
    initial = hooks.snapshot(memory)
    hooks.invalidate_session()
    reconnect = hooks.snapshot(memory)
    assert reconnect.session != initial.session
    assert reconnect.stable_polls == 1
    assert NativeHooks().snapshot(memory).session != reconnect.session


@pytest.mark.skipif(not PAIRS, reason='private original RAM captures not installed')
def test_original_awarded_b_and_physical_pickups_detect_exact_locations():
    from ..client.runtime import detect_checks
    from ..Locations import LOCATION_TABLE
    from . import generate
    first, second = next(pair for pair in PAIRS if '202546' in pair[0].name)
    state = NativeHooks().snapshot(SonicMemory(DumpBackend(first, second)))
    slot = generate({'rank_checks': 'all'}).worlds[1].fill_slot_data()
    names = {'Tropical Resort Act 1 - Clear', 'Tropical Resort Act 1 - B Rank',
             'Tropical Resort Act 1 - C Rank', 'Tropical Resort Act 1 - Red Ring 1',
             'Tropical Resort Act 1 - Red Ring 5'}
    # Act 2's result mask is active here, but has not reached the save bank.
    assert state.active_rings['stg130'] == frozenset({2, 4, 5})
    assert detect_checks(slot, state) == {LOCATION_TABLE[name].code for name in names}
