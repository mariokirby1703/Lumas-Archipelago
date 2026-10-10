import json
import random
from collections import Counter
from pathlib import Path
import tempfile

import pytest
import yaml
from BaseClasses import ItemClassification
from .. import Items, Locations
from ..Options import SonicColoursOptions, OPTION_NAMES
from ..world_constants import STAGES, NORMAL, load_data, game_land_gates, pack_rings
from ..client.staging import plan_stage_mapping
from ..client.audio import plan_music
from ..client.runtime import validate_slot, inventory
from ..client.memory import MemoryUnavailable
from . import generate


def test_catalogs():
    assert len(STAGES) == 66 and len(NORMAL) == 36
    assert len({s['mission_id'] for s in STAGES}) == 66
    assert len(load_data('wisp_capsules.json')) == 706
    rings = load_data('red_rings.json')
    counts = Counter(r['mission_id'] for r in rings)
    assert len(rings) == 180 and len(counts) == 36 and set(counts.values()) == {5}
    assert len({(r['mission_id'], r['red_ring_number']) for r in rings}) == 180
    assert any(r['layer'] != '00' for r in rings)
    for bank in ('bank_A', 'bank_B', 'bank_C'):
        assert len({s[bank] for s in load_data('progress_bits.json')}) == 66
    assert next(s for s in STAGES if s['name'] == 'Tropical Resort Act 2')['mission_id'] == 'stg130'
    assert len(set(Locations.LOCATION_TABLE[n].code for n in Locations.LOCATION_TABLE)) == len(Locations.LOCATION_TABLE)
    assert not set(Items.ITEM_TABLE.values()) & {d.code for d in Locations.LOCATION_TABLE.values()}


@pytest.mark.parametrize('reduction', range(180))
def test_thresholds(reduction):
    gates = game_land_gates(reduction)
    ordered = [gates[f'{i}-{act}'] for act in (2, 3) for i in range(1, 8)]
    assert ordered[0] >= 1 and ordered[-1] <= 180
    assert all(a < b for a, b in zip(ordered, ordered[1:]))
    assert sum(v == 0 for v in gates.values()) == 7
    if reduction == 40:
        assert ordered == list(range(10, 141, 10))


def test_options_and_yaml():
    path = Path(__file__).parents[1] / 'examples/SonicColours.yaml'
    data = yaml.safe_load(path.read_text())
    assert data['game'] == 'Sonic Colours (Wii)'
    options = data['Sonic Colours (Wii)']
    assert set(options) == set(OPTION_NAMES)
    for name, value in options.items():
        cls = SonicColoursOptions.type_hints[name]
        if name == 'starting_act':
            assert value == cls.default == 'random'
        else:
            assert cls.from_any(value).value == cls.from_any(cls.default).value
    world = generate(options, fill=True).worlds[1]
    validate_slot(world.fill_slot_data())
    assert world.multiworld.can_beat_game()
    for name in OPTION_NAMES:
        cls = SonicColoursOptions.type_hints[name]
        if hasattr(cls, 'options'):
            assert 'random' not in cls.options
            for value in cls.options:
                cls.from_any(value)


@pytest.mark.parametrize('mode,count', [('off', 73), ('singles', 253), ('per_level', 109)])
def test_counts(mode, count):
    world = generate({'red_ring_checks': mode}, fill=True).worlds[1]
    assert len(world.active_locations) == count
    assert len(world.multiworld.itempool) == count
    assert world.multiworld.can_beat_game()
    assert sum(item.name in Items.EMERALDS for item in world.multiworld.itempool) == 7
    assert all(item.classification & ItemClassification.progression for item in world.multiworld.itempool
               if item.name in Items.RING_VALUES)
    assert sum(Items.RING_VALUES.get(item.name, 0) for item in world.multiworld.itempool) == 187
    assert len(world.multiworld.precollected_items[1]) == 0


@pytest.mark.parametrize('target', range(181))
def test_exact_packing(target):
    for capacity in (target + 1, 25):
        result = pack_rings(target, capacity)
        assert sum(result) == target and len(result) <= capacity
    if target:
        with pytest.raises(ValueError):
            pack_rings(target, 0)


@pytest.mark.parametrize('settings', [
    {'red_ring_checks': 'off', 'game_land_checks': 0, 'chaos_emerald_checks': 0},
    {'red_ring_checks': 'per_level'}, {'trap_percentage': 100}, {'trap_percentage': 0},
    {'goal': 'super_sonic'}, {'starting_act': 'asteroid_coaster_act_6'},
])
def test_fill_100_seeds(settings):
    for seed in range(100):
        multiworld = generate(settings, seed, fill=True)
        assert multiworld.can_beat_game()
        assert not multiworld.get_unfilled_locations()


@pytest.mark.parametrize('option,value', [('level_randomization', 'anywhere'), ('level_randomization', 'per_world'),
    ('death_link', 1), ('swim_trap_weight', 'low')])
def test_unverified_options_fail_precisely(option, value):
    for seed in range(100):
        with pytest.raises(ValueError, match='requires_verified_hook'):
            generate({option: value}, seed)


def test_low_capacity_error_and_trap_classification():
    with pytest.raises(ValueError, match='Too few'):
        pack_rings(187, 1)
    world = generate({'trap_percentage': 100, 'ring_loss_trap_weight': 'off'}).worlds[1]
    assert not any(i.trap for i in world.multiworld.itempool)
    world = generate({'trap_percentage': 100}).worlds[1]
    assert all(i.advancement or i.trap or i.useful for i in world.multiworld.itempool)
    assert inventory([Items.ITEM_TABLE['Red Rings (+5)'], Items.ITEM_TABLE['Red Rings (+10)']])['red_rings'] == 15


def test_plans_are_bijections_and_not_native_patches():
    for mode in ('off', 'per_world', 'anywhere'):
        mapping = plan_stage_mapping(random.Random(12), mode)
        assert mapping == plan_stage_mapping(random.Random(12), mode)
        assert set(mapping.values()) == {s['mission_id'] for s in STAGES}
        for s in STAGES:
            if not s['normal']:
                assert mapping[s['stage_slot_id']] == s['mission_id']
            elif mode == 'per_world':
                assert next(t for t in STAGES if t['mission_id'] == mapping[s['stage_slot_id']])['zone_index'] == s['zone_index']
    with pytest.raises(MemoryUnavailable, match='asset_index'):
        plan_music('seed', 'anywhere', set())


def test_output_and_tamper_rejection():
    world = generate().worlds[1]
    data = world.fill_slot_data()
    assert validate_slot(json.loads(json.dumps(data))) == data
    for mutation in [dict(schema_version=999), dict(game_land_gates={}), dict(locations={}), dict(stage_mapping={})]:
        with pytest.raises(ValueError):
            validate_slot({**data, **mutation})
    with tempfile.TemporaryDirectory() as directory:
        world.generate_output(directory)
        output = json.loads(next(Path(directory).glob('*.apsonic')).read_text())
        assert output['slot_data'] == data
