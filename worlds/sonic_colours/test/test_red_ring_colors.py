import asyncio
import hashlib
import json
from copy import deepcopy

import pytest

from ..Items import ITEM_TABLE, RING_VALUES
from ..client.red_ring_colors import (COLORS, OPTION_DEFAULTS, RING_ITEM_IDS,
                                      RedRingColors, reward_color, trap_color)
from ..client.runtime import validate_slot
from ..client.client import SonicContext, slot_identity_digest
from . import generate


@pytest.mark.parametrize('mode', [0, 1, 2])
@pytest.mark.parametrize('trap_mode', [0, 1])
@pytest.mark.parametrize('receiver', [1, 2])
@pytest.mark.parametrize('flags', range(8))
@pytest.mark.parametrize('item', [ITEM_TABLE['Red Ring'], ITEM_TABLE['Rings']])
def test_reward_classification_and_precedence(mode, trap_mode, receiver, flags, item):
    options = {'own_item_red_ring_colors': mode, 'trap_red_ring_colors': trap_mode}
    result = reward_color(item, receiver, flags, 1, options, ('Seed', 0, 1), 100)
    if flags & 4:
        expected = trap_color(('Seed', 0, 1), 100) if trap_mode else 'red'
    elif receiver == 1 and (mode == 0 or mode == 1 and item in RING_ITEM_IDS):
        expected = 'red'
    else:
        expected = 'purple' if flags & 1 else 'blue' if flags & 2 else 'light_blue'
    assert result == expected


def test_currency_detection_uses_all_stable_ring_ids():
    assert RING_ITEM_IDS == {ITEM_TABLE[name] for name in RING_VALUES}
    for item in RING_ITEM_IDS:
        assert reward_color(item, 1, 1, 1, {'own_item_red_ring_colors': 1}, 'S', 1) == 'red'
    assert reward_color(987654, 2, 1, 1, {}, 'S', 1) == 'purple'
    assert reward_color(987654, 1, 1, 1, {'own_item_red_ring_colors': 1}, 'S', 1) == 'purple'


def data_for(mode=1, enabled=True):
    return generate({'red_ring_checks': mode, 'red_ring_item_colors': enabled,
                     'own_item_red_ring_colors': 2, 'trap_red_ring_colors': 1}).worlds[1].fill_slot_data()


@pytest.mark.parametrize('mode,count', [(1, 180), (2, 36)])
def test_scout_cache_modes_late_results_and_scene_reentry(mode, count):
    data = data_for(mode)
    colors = RedRingColors(data, 1, 0)
    message = colors.scout_message()
    assert message['create_as_hint'] == 0 and len(message['locations']) == count
    assert colors.stage_colors('stg110') == ('red',) * 5
    code = colors.locations['stg110', 1]
    colors.receive([(ITEM_TABLE['Rings'], code, 2, 1)])
    first = colors.stage_colors('stg110')
    assert first == (('purple',) * 5 if mode == 2 else ('purple', 'red', 'red', 'red', 'red'))
    assert colors.stage_colors('stg110') is first
    colors.stage_colors('stg130')
    assert colors.stage_colors('stg110') is first
    colors.receive([(ITEM_TABLE['Rings'], code, 2, 4)])
    updated = colors.stage_colors('stg110')
    assert updated[0] in COLORS
    if mode == 2:
        assert len(set(updated)) == 1
    restarted = RedRingColors(data, 1, 0)
    restarted.receive([(ITEM_TABLE['Rings'], code, 2, 4)])
    assert restarted.stage_colors('stg110') == updated
    assert colors.stage_colors('stg190') == ('red',) * 5
    assert colors.stage_colors('stgD10') == ('red',) * 5


def test_disabled_and_absent_locations_do_not_scout_or_touch_materials():
    colors = RedRingColors(data_for(enabled=False), 1, 0)
    assert colors.scout_message() is None
    colors.receive([(123, 456, 1, 1)])
    assert not colors.rewards and not colors.stage_cache
    assert colors.stage_colors('stg110') == ('red',) * 5
    empty = {**data_for(), 'locations': {}}
    assert RedRingColors(empty, 1, 0).scout_message() is None
    assert not colors.status()['native_rendering']


def test_malformed_or_unsolicited_scout_data_is_ignored():
    colors = RedRingColors(data_for(), 1, 0)
    code = colors.locations['stg110', 1]
    colors.receive([(1, 99, 1, 1), (1, code, 1), {'location': code},
                    (1, code, 1, True), (1, code, 0, 1), (1, code, 1, 8)])
    assert not colors.rewards


def test_trap_palette_is_stable_and_covers_three_disguises():
    identity = ('Seed', 0, 1)
    first = [trap_color(identity, code) for code in range(300)]
    assert set(first) == set(COLORS)
    assert first == [trap_color(identity, code) for code in range(300)]
    assert first != [trap_color(('OtherSeed', 0, 1), code) for code in range(300)]


def test_trap_hash_rejects_the_biased_tail(monkeypatch):
    from types import SimpleNamespace
    from ..client import red_ring_colors
    calls = []
    values = iter([(1 << 256) - 1, 1])
    def digest(data):
        calls.append(data)
        return SimpleNamespace(digest=lambda: next(values).to_bytes(32, 'big'))
    monkeypatch.setattr(red_ring_colors.hashlib, 'sha256', digest)
    assert trap_color(('Seed', 0, 1), 123) == 'blue'
    assert len(calls) == 2 and calls[0] != calls[1]


def test_legacy_slot_and_journal_identity_remain_unchanged():
    old = deepcopy(data_for())
    old['options_revision'] = 10
    for name in OPTION_DEFAULTS:
        old['options'].pop(name)
    expected = hashlib.sha256(json.dumps(old, sort_keys=True).encode()).hexdigest()
    normalized = validate_slot(old)
    assert all(normalized['options'][name] == 0 for name in OPTION_DEFAULTS)
    assert slot_identity_digest(normalized) == expected
    assert slot_identity_digest(validate_slot(normalized)) == expected
    assert not RedRingColors(normalized, 1, 0).enabled


def test_new_slot_requires_valid_explicit_color_options():
    data = data_for()
    assert data['options_revision'] == 12
    assert validate_slot(data) == data
    for name in OPTION_DEFAULTS:
        missing = deepcopy(data)
        del missing['options'][name]
        with pytest.raises(ValueError, match='options missing'):
            validate_slot(missing)
    bad = deepcopy(data)
    bad['options']['own_item_red_ring_colors'] = 3
    with pytest.raises(ValueError, match='invalid choice'):
        validate_slot(bad)


@pytest.mark.parametrize('own', [0, 1, 2])
@pytest.mark.parametrize('trap', ['red', 'random'])
def test_colors_do_not_change_items_locations_or_fill(own, trap):
    settings = {'red_ring_item_colors': True, 'own_item_red_ring_colors': own,
                'trap_red_ring_colors': trap}
    reference = generate(seed=19, fill=True)
    colored = generate(settings, seed=19, fill=True)
    locations = lambda world: {loc.name: (loc.address, loc.item.name, loc.item.code)
                               for loc in world.get_locations()}
    assert locations(reference) == locations(colored)
    assert colored.can_beat_game()


def test_trap_random_yaml_is_a_disguise_mode_not_a_random_option_roll():
    from ..Options import TrapRedRingColors
    for _ in range(20):
        option = TrapRedRingColors.from_any('random')
        assert option.value == 1 and option.current_key == 'random'
    assert TrapRedRingColors.get_option_name(1) == 'Random'


@pytest.mark.parametrize('enabled', [False, True])
def test_authenticated_scout_protocol_connect_reconnect_and_disconnect(tmp_path, enabled):
    async def scenario():
        data = data_for(enabled=enabled)
        ctx = SonicContext(journal_directory=tmp_path)
        ctx.team, ctx.slot = 0, 1
        sent = []
        async def send(messages):
            sent.extend(messages)
        ctx.send_msgs = send
        ctx.on_package('RoomInfo', {'seed_name': data['seed_name']})
        ctx.on_package('Connected', {'slot_data': data})
        await asyncio.sleep(0)
        scouts = [m for m in sent if m['cmd'] == 'LocationScouts']
        assert len(scouts) == int(enabled)
        if enabled:
            colors = ctx.runtime.red_ring_colors
            code = colors.locations['stg110', 1]
            packet = {'locations': [(ITEM_TABLE['Rings'], code, 2, 1)]}
            ctx.on_package('LocationInfo', packet)
            assert colors.stage_colors('stg110')[0] == 'purple'
            ctx.reset_server_state()
            ctx.on_package('LocationInfo', {'locations': [(ITEM_TABLE['Rings'], code, 2, 2)]})
            assert colors.stage_colors('stg110')[0] == 'purple'
            ctx.on_package('RoomInfo', {'seed_name': data['seed_name']})
            ctx.on_package('Connected', {'slot_data': data})
            await asyncio.sleep(0)
            assert not ctx.runtime.red_ring_colors.rewards
            assert len([m for m in sent if m['cmd'] == 'LocationScouts']) == 2
            sent.clear()
            await ctx.scout_red_rings(('AnotherSeed', 0, 1), ctx.runtime.red_ring_colors, scouts[0])
            assert not sent
        ctx.release_runtime()
        await ctx.shutdown()
    asyncio.run(scenario())


def test_ring_color_preparation_does_not_change_native_hook_payload():
    from ..client.native_dol import plan
    before = plan()
    colors = RedRingColors(data_for(), 1, 0)
    colors.receive([(ITEM_TABLE['Rings'], colors.locations['stg110', 1], 2, 1)])
    colors.stage_colors('stg110')
    assert plan() == before
    legacy = plan(include_ring_materials=False,include_boot_guards=False,include_accessible_colors=False)
    assert legacy[2].hex() == 'd37b812a9e186695a45db4519ebada0f557e4523dc26dcea5098d95c6ddadc47'
    from ..client.red_ring_render_test import allocation_patches
    from ..client.red_ring_spawn import patches
    ring_plan=plan(include_boot_guards=False)
    assert ring_plan[0] == legacy[0] + allocation_patches() + patches()
    assert len(before[1]) == len(legacy[1])
    assert not colors.status('stg110')['native_rendering']


def test_pal_ring_resource_strings_and_lookup_pointers(pal_dol_bytes):
    from ..client.native_dol import Dol, PAL_DOL_SHA256
    assert hashlib.sha256(pal_dol_bytes).hexdigest() == PAL_DOL_SHA256
    image = Dol(pal_dol_bytes)
    for address, pointer, name in (
            (0x8071DD60, 0x808F1E70, b'cmn_obj_starring_SD\0'),
            (0x8071DD74, 0x808F1E74, b'cmn_obj_starring_hide_SD\0'),
            (0x8071DD90, 0x808F1E78, b'obj_redring\0')):
        assert image.read(address, len(name)) == name
        assert image.read(pointer, 4) == address.to_bytes(4, 'big')
    # Verified metadata/initializer instructions, not a proven render callback.
    assert image.read(0x801D69AC, 4).hex() == '3c808077'
    assert image.read(0x801D69B4, 4).hex() == '3884f9d0'
    assert image.read(0x801D6DFC, 8).hex() == '3ca0807738a5fab8'
    assert image.read(0x801D6E4C, 4).hex() == '90be0000'
    assert image.read(0x8076FAC0, 4).hex() == '801d6f00'
