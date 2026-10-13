"""World-access /give & /remove aliases with the real local inventory and command handler.

Uses the existing AP-Core-free command test harness.  The world roster below
matches Items.WORLD_ITEMS for PAL Sonic Colours; no new item IDs are created.
"""
import pytest
from .test_give_remove_quiet_output import environment

WORLD_UNLOCKS = (
    ('Sweet Mountain Shuttle', ('sweet', 'sweet mountain', 'world sweet', 'sweet mountain access')),
    ('Starlight Carnival Shuttle', ('starlight', 'starlight carnival', 'world starlight')),
    ('Planet Wisp Shuttle', ('planet', 'planet wisp', 'world planet')),
    ('Aquarium Park Shuttle', ('aquarium', 'aquarium park', 'world aquarium')),
    ('Asteroid Coaster Shuttle', ('asteroid', 'asteroid coaster', 'world asteroid')),
)


@pytest.mark.parametrize('item,aliases', WORLD_UNLOCKS)
def test_world_access_single_item_and_aliases(monkeypatch, item, aliases):
    run, overlay, genuine = environment(monkeypatch)
    for alias in aliases:
        assert run('give', alias) == f'Given: {item}.'
        assert overlay.apply(genuine)['counts'][item] == 1
        assert run('give', alias) == f'No change: {item} already unlocked.'
        assert run('remove', alias) == f'Removed: {item}.'
        assert overlay.apply(genuine)['counts'][item] == 0
        assert run('remove', alias) == f'No change: {item} already removed.'


@pytest.mark.parametrize('alias', ('world', 'worlds', 'all worlds',
                                   'world access', 'all world access',
                                   'shuttles', 'all shuttles'))
def test_world_group_only_touches_unlockable_worlds(monkeypatch, alias):
    run, overlay, genuine = environment(monkeypatch)
    from sonic_colours.client.test_inventory import WORLD_UNLOCK_ITEMS
    assert len(WORLD_UNLOCK_ITEMS) == 5
    assert run('give', alias) == 'Given: all World Shuttles.'
    c = overlay.apply(genuine)['counts']
    assert all(c[w] == 1 for w in WORLD_UNLOCK_ITEMS)
    assert c['Double Jump'] == 0 and c['Cyan Laser Wisp'] == 0
    assert run('give', alias) == 'No change: all World Shuttles already unlocked.'
    assert run('remove', alias) == 'Removed: all World Shuttles.'
    c = overlay.apply(genuine)['counts']
    assert all(c[w] == 0 for w in WORLD_UNLOCK_ITEMS)
    assert run('remove', alias) == 'No change: all World Shuttles already removed.'


def test_world_remove_masks_real_receipt_but_reset_restores(monkeypatch):
    run, overlay, genuine = environment(monkeypatch)
    genuine['counts']['Sweet Mountain Shuttle'] = 1
    genuine['counts']['Asteroid Coaster Shuttle'] = 1
    assert run('remove', 'sweet') == 'Removed: Sweet Mountain Shuttle.'
    assert genuine['counts']['Sweet Mountain Shuttle'] == 1
    assert overlay.apply(genuine)['counts']['Sweet Mountain Shuttle'] == 0
    assert run('give', 'sweet') == 'Given: Sweet Mountain Shuttle.'
    assert overlay.apply(genuine)['counts']['Sweet Mountain Shuttle'] == 1
    assert run('remove', 'worlds') == 'Removed: all World Shuttles.'
    assert overlay.apply(genuine)['counts']['Asteroid Coaster Shuttle'] == 0
    overlay.reset()
    assert overlay.apply(genuine)['counts']['Sweet Mountain Shuttle'] == 1
    assert overlay.apply(genuine)['counts']['Asteroid Coaster Shuttle'] == 1


def test_starter_and_terminal_are_not_false_positive_unlocks(monkeypatch):
    run, overlay, genuine = environment(monkeypatch)
    for verb, name, term in [('remove', 'tropical', 'Tropical Resort'),
                             ('give', 'terminal', 'Terminal Velocity')]:
        output = run(verb, name)
        assert output.startswith(('Remove failed:', 'Give failed:'))
        assert term in output
    assert not overlay.deltas


def test_all_abilities_does_not_silently_grant_worlds(monkeypatch):
    run, overlay, genuine = environment(monkeypatch)
    assert run('give', 'all') == 'Given: all abilities.'
    assert overlay.apply(genuine)['counts']['Sweet Mountain Shuttle'] == 0
    assert run('give', 'worlds') == 'Given: all World Shuttles.'
    assert overlay.apply(genuine)['counts']['Sweet Mountain Shuttle'] == 1
    assert run('remove', 'all') == 'Removed: all abilities.'
    assert overlay.apply(genuine)['counts']['Sweet Mountain Shuttle'] == 1
