from collections import Counter
from dataclasses import replace
import tempfile
import pytest

from BaseClasses import CollectionState
from .. import Items, Locations
from ..capsules import CAPSULES, build_catalog, instance_key
from ..world_constants import GAME, BASE_ID, load_data
from ..client.journal import Journal
from ..client.state import SaveGuard, PlaythroughState
from ..client.hooks import NativeHooks
from ..client.memory import SonicMemory, MemoryUnavailable
from ..client.runtime import Runtime, inventory, detect_checks
from . import generate
from .test_memory import FakeBackend
from .test_runtime import IDENTITY, snapshot


def test_default_wisps_shuffle_in_reachable_spheres_for_100_seeds():
    for seed in range(100):
        multiworld = generate(seed=seed, fill=True)
        assert not multiworld.precollected_items[1]
        assert Counter(i.name for i in multiworld.itempool if i.name in Items.WISP_ITEMS) == Counter(Items.WISP_ITEMS)
        spheres = list(multiworld.get_spheres())
        obtained = {location.item.name for sphere in spheres for location in sphere if location.item}
        assert set(Items.WISP_ITEMS) <= obtained
        assert any(l.address is not None for l in spheres[0])
        assert multiworld.can_beat_game()
    world = generate({'wisp_unlocks': 'vanilla'}).worlds[1]
    assert not any(i.name in Items.WISP_ITEMS for i in world.multiworld.itempool)


def test_removed_features_leave_holes_in_ids_and_options():
    from ..Options import SonicColoursOptions, RankChecks, Goal
    assert 'super_sonic_item' not in SonicColoursOptions.type_hints
    assert 'd' not in RankChecks.options and 'super_sonic' not in Goal.options
    assert BASE_ID + 22 not in Items.BY_ID
    assert Items.ITEM_TABLE['Red Ring (+1)'] == BASE_ID + 23
    assert not any(name.endswith(' - D Rank') for name in Locations.LOCATION_TABLE)
    assert sum(d.kind == 'rank' for d in Locations.LOCATION_TABLE.values()) == 176
    assert GAME == 'Sonic Colours (Wii)'
    assert not inventory([Items.ITEM_TABLE[n] for n in Items.EMERALDS[:-1]])['super_sonic_allowed']
    assert inventory([Items.ITEM_TABLE[n] for n in Items.EMERALDS])['super_sonic_allowed']


def test_capsule_identity_candidates_and_validation_gates():
    assert len(CAPSULES) == 706
    assert sum(c.story for c in CAPSULES.values()) == 456
    assert sum(c.exclusion == 'mission_unmapped' for c in CAPSULES.values()) == 18
    assert sum(bool(c.name) and not c.story for c in CAPSULES.values()) == 232
    assert len({c.code for c in CAPSULES.values()}) == 706
    assert sum(c.eligible for c in CAPSULES.values()) == 680
    assert sum(c.eligible and c.story for c in CAPSULES.values()) == 448
    assert all(__import__("json").loads(c.key)[2] == "00" for c in CAPSULES.values() if c.eligible)
    rows = load_data('wisp_capsules.json')[:2]
    with pytest.raises(ValueError, match='duplicate'):
        build_catalog([rows[0], rows[0]], {})
    key = instance_key(rows[0])
    with pytest.raises(ValueError, match='proof'):
        build_catalog(rows, {key: {'validated': True}})
    for mode in ('story', 'all'):
        world = generate({'wisp_capsule_sanity': mode}).worlds[1]
        expected = 448 if mode == 'story' else 680
        assert sum(Locations.LOCATION_TABLE[n].kind == 'capsule' for n in world.fill_slot_data()['locations']) == expected


def test_capsule_opening_is_instance_and_permission_specific(monkeypatch):
    from ..client.runtime import capsule_check_allowed
    candidates = [c for c in CAPSULES.values() if c.mission == 'stg110'][:2]
    for c in candidates:
        monkeypatch.setitem(CAPSULES, c.key, replace(c, eligible=True, exclusion=None, wisp_item='Cyan Laser Wisp'))
    data = {'options': {'wisp_unlocks': 1}, 'locations': {
        c.name: c.code for c in candidates}}
    state = snapshot(opened_capsules=frozenset({candidates[0].key}))
    assert not detect_checks(data, state)
    result = detect_checks(data, state, frozenset({'Cyan Laser Wisp'}))
    assert result == {candidates[0].code}
    assert detect_checks(data, state, frozenset({'Cyan Laser Wisp'})) == result
    data['options']['wisp_unlocks'] = 0
    assert detect_checks(data, state) == result


def test_typed_evidence_has_no_unproven_promotion():
    from ..client.evidence import evidence_registry, EvidenceGrade
    records = evidence_registry()
    assert records['manager_global'].grade == EvidenceGrade.CODE_DERIVED
    assert records['runtime_rings'].grade == EvidenceGrade.DUMP_CORRELATED
    assert records['new_game_indicator'].grade == EvidenceGrade.DUMP_CORRELATED
    assert not any(r.live_write for r in records.values())
    assert {name for name, r in records.items() if r.live_read} == {'validated_clear_bits'}


def test_new_game_prologue_any_slot_binding_resume_and_switch():
    data = generate().worlds[1].fill_slot_data()
    class Hooks:
        value = snapshot()
        def snapshot(self, memory): return self.value
        def project_permissions(self, *args): raise MemoryUnavailable('native permissions awaiting proof')
    hooks = Hooks()
    with tempfile.TemporaryDirectory() as directory:
        with Journal(directory, IDENTITY) as journal:
            guard = SaveGuard(journal)
            runtime = Runtime(data, journal, guard, hooks)
            memory = SonicMemory(FakeBackend())
            guard.confirm_new_game()
            hooks.value = snapshot(save_identity=None, visible_slot=None, actual_mission='stg110', new_game_verified=True,
                scene_verified=True, fresh_fields=(True, True), progress_verified=True,
                persisted_clears=frozenset({'stg110'}))
            assert runtime.poll(memory, [], False) == (set(), False)
            assert guard.state == PlaythroughState.MANDATORY_PROLOGUE
            assert journal.data['bootstrap']['checks'] == [Locations.LOCATION_TABLE['Tropical Resort Act 1 - Clear'].code]
            hooks.value = replace(hooks.value, persisted_clears=frozenset({'stg110', 'stg130'}), scene='save_selection')
            runtime.poll(memory, [], False)
            assert guard.state == PlaythroughState.VANILLA_SAVE_SELECTION
            assert len(journal.data['bootstrap']['checks']) == 2 and not journal.data['checks']
            hooks.value = replace(hooks.value, scene='world_map', save_identity='verified-save-slot-three',
                                  visible_slot=3, save_identity_verified=True, new_save_selected=True)
            checks, goal = runtime.poll(memory, [], True)
            assert len(checks) == 2 and not goal and guard.armed
            assert journal.data['save_identity'] == 'verified-save-slot-three'
            assert 'native permissions awaiting proof' in runtime.last_error
            checks, goal = runtime.poll(memory, [], True)
            assert len(checks) == 2 and not goal
            bound = hooks.value
            hooks.value = replace(bound, save_identity='other-save')
            assert runtime.poll(memory, [], True) == (set(), False)
            assert not guard.armed and guard.state == PlaythroughState.UNSAFE
        with Journal(directory, IDENTITY) as journal:
            guard = SaveGuard(journal)
            runtime = Runtime(data, journal, guard, hooks)
            hooks.value = replace(bound, session='new-emulator-session')
            assert len(runtime.poll(memory, [], True)[0]) == 2
            assert guard.state == PlaythroughState.RESUME
            hooks.value = replace(hooks.value, persisted_clears=frozenset({'stg110'}))
            assert runtime.poll(memory, [], True) == (set(), False)
            assert 'rollback' in guard.reason and not guard.armed


def test_bootstrap_confirmation_cannot_claim_existing_save():
    with tempfile.TemporaryDirectory() as directory, Journal(directory, IDENTITY) as journal:
        guard = SaveGuard(journal)
        guard.confirm_new_game()
        guard.observe(snapshot(save_identity_verified=True, progress_verified=True, scene_verified=True))
        assert journal.data['save_identity'] is None and not guard.armed
        assert not guard.can_record(snapshot())


def test_native_snapshot_reads_candidate_chain_without_promoting_it():
    from ..client.versions import VERSION
    backend = FakeBackend()
    def put(a, n): backend.put(a, n.to_bytes(4, 'big'))
    put(VERSION['manager_global_candidate'], 0x90000100)
    put(0x90000130, 0x90001000)
    put(0x90001008 + 0x1c + 0x20, 1 << 22)
    memory = SonicMemory(backend)
    memory.verify_revision = lambda: 'test-only-executable'
    hooks = NativeHooks()
    for _ in range(3): state = hooks.snapshot(memory)
    assert state.candidate_clears == frozenset({'stg110'})
    assert state.stable_polls == 3 and not state.progress_verified
    assert not state.persisted_clears
    assert state.save_identity is None and state.visible_slot is None
    assert not backend.writes


def test_emerald_rewards_need_all_three_native_clears_and_logical_events():
    data = generate({'game_land_checks': False}).worlds[1].fill_slot_data()
    from ..world_constants import STAGES
    missions = [s['mission_id'] for s in STAGES if s['zone_index'] == 7]
    reward = snapshot(emerald_rewards=frozenset({1}), persisted_clears=frozenset(missions[2:]))
    code = Locations.LOCATION_TABLE['Game Land 1 - Chaos Emerald Obtained'].code
    assert code not in detect_checks(data, reward)
    reward = replace(reward, persisted_clears=frozenset(missions))
    assert code in detect_checks(data, reward)
    multiworld = generate({'game_land_checks': False})
    state = CollectionState(multiworld)
    for _ in range(14): state.collect(multiworld.worlds[1].create_item('Red Rings (+10)'), prevent_sweep=True)
    location = multiworld.get_location('Game Land 1 - Chaos Emerald Obtained', 1)
    assert not location.access_rule(state)
    state.sweep_for_advancements()
    assert location.access_rule(state)
