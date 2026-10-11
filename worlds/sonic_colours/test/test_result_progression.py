"""Permission timing regression, not an assertion of live path animation."""
from dataclasses import replace
import pytest
from ..world_constants import STAGES
from ..world_progression import available_story_stages, progression_clears
from ..client.state import Snapshot


@pytest.mark.parametrize('zone', range(6))
@pytest.mark.parametrize('mode', [0, 1])
def test_sixth_final_result_enables_boss_before_save(zone, mode):
    acts = [s['mission_id'] for s in STAGES if s['zone_index'] == zone and s['slot'] <= 6]
    boss = next(s['mission_id'] for s in STAGES if s['zone_index'] == zone and s['slot'] == 7)
    s = Snapshot('session', 'save', 2, 'results', acts[-1], scene_verified=True,
        persisted_clears=frozenset(acts[:-1]), current_result={
            'mission':acts[-1], 'grade':2, 'final':True,
            'provenance':'stage9C_native_UI_state7_grade124'})
    assert boss not in available_story_stages(zone, s.persisted_clears, mode)
    assert boss in available_story_stages(zone, progression_clears(s), mode)
    assert s.persisted_clears == frozenset(acts[:-1])
    for changes in ({'scene':'gameplay'}, {'scene_verified':False},
                    {'actual_mission':acts[0]},
                    {'current_result':{**s.current_result, 'final':False}},
                    {'current_result':{**s.current_result, 'grade':True}},
                    {'current_result':{**s.current_result, 'provenance':'unverified'}}):
        assert boss not in available_story_stages(zone, progression_clears(replace(s, **changes)), mode)
    # Partial completion never grants the boss, even on a final result.
    assert boss not in available_story_stages(zone, progression_clears(replace(s, persisted_clears=frozenset(acts[:2]))), mode)


@pytest.mark.parametrize('final', [False, True])
def test_results_write_guard_projects_boss_flag_only_after_verified_final(final):
    from .test_memory import FakeBackend
    from . import generate
    from ..client.memory import SonicMemory, MemoryUnavailable
    from ..client.state import WritePolicy
    from ..client.hooks import NativeHooks
    from ..client.runtime import inventory
    from ..world_constants import load_data
    backend = FakeBackend(); memory = SonicMemory(backend)
    chain = (0x90001000, 0x90002000, 0, 0x90004000)
    memory.resolve_flags_ptr = lambda **kwargs: chain
    memory.verify_revision = lambda: None
    acts = [s['mission_id'] for s in STAGES if s['zone_index'] == 0 and s['slot'] <= 6]
    s = Snapshot('session', 'save', 2, 'results', acts[-1], scene_verified=True,
        persisted_clears=frozenset(acts[:-1]), evidence={'chain':chain},
        current_result={'mission':acts[-1], 'grade':2, 'final':final,
                       'provenance':'stage9C_native_UI_state7_grade124'})
    class Guard:
        def check(self, snapshot): return 'fixture attributed save'
    memory.write_guard = WritePolicy(memory, Guard(), lambda _: s)
    hooks = NativeHooks()
    slot = generate({'world_progression':'open_acts'}).worlds[1].fill_slot_data()
    before = dict(backend.data)
    if not final:
        with pytest.raises(MemoryUnavailable, match='unsafe permission scene'):
            hooks.project_permissions(memory, s, inventory([]), slot)
        assert backend.data == before
        return
    hooks.project_permissions(memory, s, inventory([]), slot)
    boss = next(stage['mission_id'] for stage in STAGES if stage['zone_index'] == 0 and stage['slot'] == 7)
    bit = int(next(row['bank_A'] for row in load_data('progress_bits.json') if row['mission'] == boss))
    assert memory.read_progress_bit(chain[-1], bit)
    # Only the reviewed permission bank is changed; completion records remain native.
    assert all(chain[-1]+0x10 <= address < chain[-1]+0x30 for address in backend.data)
    assert s.persisted_clears == frozenset(acts[:-1])

