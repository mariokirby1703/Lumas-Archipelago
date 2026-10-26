"""Compatibility and native-control regressions. Tests must run with Archipelago Core.

Do not mistake these generator/host tests for live Wii-PAL/Dolphin evidence.
"""
from collections import Counter
from types import SimpleNamespace

from ..client.deathlink import DeathLink
from ..client.test_inventory import LocalInventoryOverrides,parse_item_request
from .. import logic
from ..world_constants import load_data
from ..Items import ALL_WISP_ITEMS


class State:
    def __init__(self, *items):
        self.items = Counter(items)

    def has(self, item, player, count=1):
        return self.items[item] >= count

    def count(self, item, player):
        return self.items[item]


def _world(**options):
    return SimpleNamespace(player=1, options=SimpleNamespace(**{
        'boost_lock': True, 'movement_unlocks': True,
        'game_land_checks': True, **options}))


def test_actual_sheet_or_routes_do_not_require_incompatible_alternatives():
    manifest = load_data('logic_from_sheet_v3.json')
    assert logic.check(_world(), State('Progressive Green Hover Wisp'),
                          manifest, 'stg320:ring:4')
    assert logic.check(_world(), State('Progressive Pink Spikes Wisp','Progressive Rail',
                                         *(['Progressive Stunts']*5)),
                          manifest, 'stg410')
    assert logic.check(_world(), State('White Boost Wisp', 'Cyan Laser Wisp',
                                         'Progressive Stunts', 'Progressive Stunts',
                                         'Progressive Stunts', 'Progressive Stunts',
                                         'Progressive Stunts'), manifest, 'stg430')
    assert not logic.check(_world(), State('Cyan Laser Wisp'), manifest, 'stg430')


def test_test_wisp_group_matches_actual_yaml_items():
    from ..wisps import required_wisp_items
    for movement in (False, True):
        for boost in (False, True):
            opts = {'movement_unlocks': movement, 'boost_lock': boost}
            overrides = LocalInventoryOverrides(opts)
            genuine = {'counts': Counter(), 'red_rings': 0, 'emeralds': [], 'wisps': []}
            overrides.change_ability_group('give', 'wisps', genuine)
            counts = overrides.apply(genuine)['counts']
            active = set(required_wisp_items(opts))
            assert all(counts[name] == (2 if name.startswith('Progressive ') else 1)
                       for name in active)
            assert all(counts[name] == 0 for name in set(ALL_WISP_ITEMS) - active)
            overrides.change_ability_group('remove', 'wisps', genuine)
            assert all(overrides.apply(genuine)['counts'][name] == 0 for name in ALL_WISP_ITEMS)
    assert parse_item_request('drill', {'movement_unlocks': False}) == ('Yellow Drill Wisp', 1)
    assert parse_item_request('drill', {'movement_unlocks': True}) == ('Progressive Yellow Drill Wisp', 1)
    assert parse_item_request('Progressive Yellow Drill Wisp', {'movement_unlocks': False}) == ('Progressive Yellow Drill Wisp', 1)


def test_uncertain_native_death_request_never_releases_echo_suppression():
    journal = SimpleNamespace(data={'remote_deaths': [], 'remote_cycle': False}, save=lambda: None)
    link = DeathLink(journal)
    for t in range(3):
        assert not link.poll(safe=True, native_state='alive', now=t, kill=lambda: 1, native_sequence=0)
    assert link.receive({'source': 'peer', 'time': 1}, 3)
    assert not link.poll(safe=True, native_state='alive', now=3, kill=lambda: 7, native_sequence=0)
    for t in range(4, 37):
        assert not link.poll(safe=True, native_state='alive', now=t,
                             kill=lambda: 7, native_sequence=0, cancel=lambda: None)
    assert link.remote_cycle and journal.data['remote_cycle']
    # A death finally witnessed belongs to the remote request and must not echo.
    assert not link.poll(safe=True, native_state='dying', now=37, kill=lambda: 7, native_sequence=1)
    for t in range(38, 41):
        assert not link.poll(safe=True, native_state='alive', now=t, kill=lambda: 7, native_sequence=1)
    assert not link.remote_cycle
    assert link.poll(safe=True, native_state='dying', now=41, kill=lambda: 7, native_sequence=2)


def test_failed_cancel_keeps_remote_cycle_until_native_witness():
    journal = SimpleNamespace(data={'remote_deaths': [], 'remote_cycle': False}, save=lambda: None)
    link = DeathLink(journal)
    for t in range(3):link.poll(safe=True, native_state='alive', now=t, kill=lambda: 1, native_sequence=0)
    link.receive({'source':'peer','time':2},3)
    link.poll(safe=True, native_state='alive', now=3, kill=lambda: 1, native_sequence=0)
    def failure():raise RuntimeError('guest stage switched')
    link.poll(safe=True, native_state='alive', now=35, kill=lambda:1,
              native_sequence=0, cancel=failure)
    assert link.remote_cycle and 'cancel not verified' in link.last_error


def test_legacy_capsule_reconciler_accepts_normal_wisp_and_unlocked_white():
    from ..capsules import CAPSULES
    from ..client.runtime import capsule_check_allowed
    from ..Locations import LocationData
    yellow = next(c for c in CAPSULES.values()
                  if c.eligible and c.wisp_item == 'Progressive Yellow Drill Wisp')
    white = next(c for c in CAPSULES.values()
                 if c.eligible and c.wisp_item == 'White Boost Wisp')
    snap = SimpleNamespace(opened_capsules=frozenset({yellow.key, white.key}))
    yellow_data = LocationData(yellow.code, yellow.mission, 'capsule', instance_key=yellow.key)
    white_data = LocationData(white.code, white.mission, 'capsule', instance_key=white.key)
    slot = {'options': {'boost_lock': False, 'movement_unlocks': False}}
    assert capsule_check_allowed(slot, yellow_data, snap, {'Yellow Drill Wisp'})
    assert not capsule_check_allowed(slot, yellow_data, snap, set())
    assert capsule_check_allowed(slot, white_data, snap, set())
    slot['options']['boost_lock'] = True
    assert not capsule_check_allowed(slot, white_data, snap, set())
    assert capsule_check_allowed(slot, white_data, snap, {'White Boost Wisp'})
