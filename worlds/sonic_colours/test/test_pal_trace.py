"""Production adapter replay and failure localization, without live writes."""
import json
from pathlib import Path

import pytest

from ..client.hooks import NativeHooks
from ..client.memory import SonicMemory
from ..client.versions import VERSION
from .test_memory import FakeBackend


@pytest.mark.parametrize('value,reason', [(0, 'zero'), (0x90000001, 'alignment'),
                                        (0x70000000, 'outside_MEM1_MEM2')])
def test_manager_failure_identifies_raw_value(value, reason):
    backend = FakeBackend()
    backend.put(VERSION['manager_global_candidate'], value.to_bytes(4, 'big'))
    trace = SonicMemory(backend).trace_save_chain()
    assert trace['first_failure']['step'] == 'manager'
    assert trace['first_failure']['raw'] == f'0x{value:08X}'
    assert trace['first_failure']['reason'] == reason
    assert trace['chain'] is None and not backend.writes


def test_null_container_is_not_mislabeled_as_menu():
    backend = FakeBackend()
    backend.put(VERSION['manager_global_candidate'], (0x90000100).to_bytes(4, 'big'))
    trace = SonicMemory(backend).trace_save_chain()
    assert trace['first_failure']['step'] == 'container'
    assert trace['first_failure']['reason'] == 'zero'
    assert trace['scene'] == 'unresolved'


def test_bad_selected_index():
    backend = FakeBackend()
    backend.put(VERSION['manager_global_candidate'], (0x90000100).to_bytes(4, 'big'))
    backend.put(0x90000130, (0x90001000).to_bytes(4, 'big'))
    backend.put(0x90001000, b'\xff')
    trace = SonicMemory(backend).trace_save_chain()
    assert trace['first_failure']['reason'] == 'index_out_of_range'


@pytest.mark.parametrize('failure,reason', [('short', 'short_read'), ('unmapped', 'read_failed')])
def test_c_bank_read_failure_is_localized(failure, reason):
    backend = FakeBackend()
    backend.put(VERSION['manager_global_candidate'], (0x90000100).to_bytes(4, 'big'))
    backend.put(0x90000130, (0x90001000).to_bytes(4, 'big'))
    original = backend.read_bytes
    def read(address, size):
        if size == 40:
            if failure == 'short':
                return bytes(39)
            raise OSError('unmapped guest data')
        return original(address, size)
    backend.read_bytes = read
    trace = SonicMemory(backend).trace_save_chain()
    assert trace['first_failure']['step'] == 'c_bank'
    assert trace['first_failure']['reason'] == reason


def test_chain_switch_during_poll_is_rejected():
    backend = FakeBackend()
    backend.put(VERSION['manager_global_candidate'], (0x90000100).to_bytes(4, 'big'))
    backend.put(0x90000130, (0x90001000).to_bytes(4, 'big'))
    original = backend.read_bytes
    def read(address, size):
        value = original(address, size)
        if size == 40:
            backend.put(0x90001000, b'\x01')
        return value
    backend.read_bytes = read
    memory = SonicMemory(backend)
    memory.verify_revision = lambda: 'fixture'
    state = NativeHooks().snapshot(memory)
    assert state.evidence['save_chain_trace']['first_failure']['step'] == 'context_recheck'
    assert not state.candidate_clears and not state.progress_verified


@pytest.mark.parametrize('filename', ['live_pal_act1.json', 'live_pal_act1_result.json',
    'live_pal_save_selection.json', 'live_pal_save_selection_pool.json', 'live_pal_world_map_slot2.json',
    'live_pal_world_map_slot2_reloaded.json', 'live_pal_act3.json', 'live_pal_act3_result.json',
    'live_pal_act3_saved.json', 'live_pal_act3_reloaded.json'])
def test_recorded_pal_reads_through_production_adapter(filename):
    report = json.loads((Path(__file__).parents[1] / 'docs' / filename).read_text())
    hooks = NativeHooks()
    for sample in report['samples']:
        recorded_bytes = {}
        for read in sample['reads']:
            for offset, value in enumerate(bytes.fromhex(read['hex'])):
                address = read['address'] + offset
                assert recorded_bytes.get(address, value) == value, 'sample changed midpoll'
                recorded_bytes[address] = value
        class Replay:
            def read_bytes(self, address, size):
                return bytes(recorded_bytes[address + offset] for offset in range(size))
            def write_bytes(self, *args):
                pytest.fail('recorded read trace must never write')
        memory = SonicMemory(Replay())
        # Executable SHA was validated by the live probe; copyrighted executable
        # bytes are deliberately absent from these bounded data-only fixtures.
        memory.verify_revision = lambda: report['revision_sha']
        state = hooks.snapshot(memory)
        assert sorted(state.candidate_clears) == sample['snapshot']['candidate_clears']
        assert state.evidence['chain'] == tuple(sample['snapshot']['evidence']['chain'])
        assert state.progress_verified and not state.scene_verified
        assert state.persisted_clears <= frozenset({'stg110', 'stg130', 'stg120'})
        assert state.save_identity is None and state.actual_mission is None


def test_real_intro_save_and_reload_bit_transitions():
    from ..tools.compare_pal_traces import compare
    docs = Path(__file__).parents[1] / 'docs'
    read = lambda name: json.loads((docs / name).read_text())
    changes = compare(read('live_pal_act1.json'), read('live_pal_world_map_slot2.json'))['changed_bits']
    assert {'bit': 150, 'before': False, 'after': True} in changes
    assert {'bit': 151, 'before': False, 'after': True} in changes
    assert compare(read('live_pal_world_map_slot2.json'),
                   read('live_pal_world_map_slot2_reloaded.json'))['changed_bits'] == []


def test_regular_act3_live_clear_and_reload():
    from ..tools.compare_pal_traces import compare
    docs = Path(__file__).parents[1] / 'docs'
    read = lambda name: json.loads((docs / name).read_text())
    assert compare(read('live_pal_act3.json'), read('live_pal_act3_result.json'))['changed_bits'] == []
    changes = compare(read('live_pal_act3.json'), read('live_pal_act3_saved.json'))['changed_bits']
    assert {'bit': 152, 'before': False, 'after': True} in changes
    assert not any(c['bit'] in (150, 151) for c in changes)
    assert compare(read('live_pal_act3_saved.json'), read('live_pal_act3_reloaded.json'))['changed_bits'] == []


def test_real_clear_reads_do_not_bypass_native_identity_gate(tmp_path):
    from ..client.journal import Journal
    from ..client.runtime import Runtime
    from ..client.state import SaveGuard
    from . import generate
    report = json.loads((Path(__file__).parents[1] / 'docs' / 'live_pal_act3_reloaded.json').read_text())
    backend = FakeBackend()
    for read in report['samples'][-1]['reads']:
        backend.put(read['address'], bytes.fromhex(read['hex']))
    memory = SonicMemory(backend)
    memory.verify_revision = lambda: report['revision_sha']
    with Journal(tmp_path, {'seed': 'live-replay-test', 'team': 0, 'slot': 1,
                            'revision': report['revision_sha']}) as journal:
        guard = SaveGuard(journal)
        guard.confirm_new_game()
        runtime = Runtime(generate().worlds[1].fill_slot_data(), journal, guard, NativeHooks())
        for _ in range(3):
            assert runtime.poll(memory, [], True) == (set(), False)
        assert runtime.snapshot.persisted_clears == frozenset({'stg110', 'stg130', 'stg120'})
        assert not guard.armed and journal.data['save_identity'] is None
        assert not journal.data['checks'] and not backend.writes
