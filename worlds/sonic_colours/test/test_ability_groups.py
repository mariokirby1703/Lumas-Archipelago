"""Live command-path tests for scoped /give and /remove batches.

Use only a minimal Items stub; no AP Core required.  This executes the actual
SonicCommands._change_test_ability AST with LocalInventoryOverrides instead
of reproducing its decisions in test code.
"""
from collections import Counter
import pytest
from .test_give_remove_quiet_output import environment


@pytest.mark.parametrize('alias', ['wisps', 'wisp', 'all wisps', 'all wisp', 'ALL_WISPS'])
def test_give_and_remove_every_wisp(alias, monkeypatch):
    run, overlay, base = environment(monkeypatch)
    from sonic_colours.Items import WISP_ITEMS, MOVEMENT_ITEMS
    assert len(WISP_ITEMS) == 8
    assert run('give', alias) == 'Given: all Wisps.'
    derived = overlay.apply(base)['counts']
    assert all(derived[name] == 1 for name in WISP_ITEMS)
    assert all(derived[name] == 0 for name in MOVEMENT_ITEMS)
    assert run('give', 'wisps') == 'No change: all Wisps already unlocked.'
    assert run('remove', alias) == 'Removed: all Wisps.'
    assert all(overlay.apply(base)['counts'][name] == 0 for name in WISP_ITEMS)
    assert run('remove', 'wisps') == 'No change: all Wisps already removed.'


@pytest.mark.parametrize('alias', ['movements', 'movement', 'moves',
                                  'all movements', 'all movement abilities'])
def test_movement_group_maximum_and_separate_wisps(alias, monkeypatch):
    run, overlay, base = environment(monkeypatch)
    from sonic_colours.Items import WISP_ITEMS, MOVEMENT_ITEMS
    from sonic_colours.client.test_inventory import MAXIMUM
    assert run('give', alias) == 'Given: all Movement abilities (max level).'
    effective = overlay.apply(base)['counts']
    assert all(effective[name] == MAXIMUM.get(name, 1) for name in MOVEMENT_ITEMS)
    assert effective['Progressive Crouch'] == 2
    assert effective['Progressive Breathing'] == 5
    assert effective['Breath'] == 0  # never enable retired 30-second tier
    assert all(effective[name] == 0 for name in WISP_ITEMS)
    assert run('remove', alias) == 'Removed: all Movement abilities.'
    assert all(overlay.apply(base)['counts'][name] == 0 for name in MOVEMENT_ITEMS)


def test_batch_remove_masks_real_ap_inventory_and_reset(monkeypatch):
    run, overlay, base = environment(monkeypatch)
    from sonic_colours.Items import WISP_ITEMS, MOVEMENT_ITEMS
    base['counts'].update({'White Boost Wisp': 1, 'Cyan Laser Wisp': 1,
                           'Double Jump': 1, 'Progressive Crouch': 2,
                           'Progressive Breathing': 4, 'Breath': 1})
    assert run('remove', 'all wisps') == 'Removed: all Wisps.'
    assert all(overlay.apply(base)['counts'][name] == 0 for name in WISP_ITEMS)
    assert overlay.apply(base)['counts']['Double Jump'] == 1
    assert run('remove', 'all movements') == 'Removed: all Movement abilities.'
    effective = overlay.apply(base)['counts']
    assert all(effective[name] == 0 for name in MOVEMENT_ITEMS)
    assert effective['Breath'] == 0
    # Server inventory was never altered.
    assert base['counts']['White Boost Wisp'] == 1
    assert base['counts']['Double Jump'] == 1
    assert base['counts']['Breath'] == 1
    assert base['counts']['Progressive Breathing'] == 4
    overlay.reset()
    restored = overlay.apply(base)['counts']
    assert restored['White Boost Wisp'] == 1
    assert restored['Progressive Breathing'] == 4
    assert restored['Breath'] == 1


def test_group_give_masks_received_legacy_breath_and_old_manual_breath(monkeypatch):
    run, overlay, base = environment(monkeypatch)
    base['counts']['Breath'] = 1
    assert run('give', 'movement') == 'Given: all Movement abilities (max level).'
    c = overlay.apply(base)['counts']
    assert c['Breath'] == 0 and c['Progressive Breathing'] == 5
    # If legacy Breath was locally given by an earlier /give all, the
    # movement group must still be able to mask it.
    overlay.reset()
    base['counts']['Breath'] = 0
    overlay.change('give', 'Breath', 1, base)
    assert overlay.apply(base)['counts']['Breath'] == 1
    assert run('give', 'movements') == 'Given: all Movement abilities (max level).'
    c = overlay.apply(base)['counts']
    assert c['Breath'] == 0 and c['Progressive Breathing'] == 5


def test_existing_single_item_aliases_and_all_command_unchanged(monkeypatch):
    run, overlay, base = environment(monkeypatch)
    assert run('give', 'laser') == 'Given: Cyan Laser Wisp.'
    assert run('give', 'breath 2') == 'Given: Progressive Breathing (level 2).'
    assert overlay.apply(base)['counts']['Progressive Breathing'] == 2
    assert run('give', 'all') == 'Given: all abilities.'
    assert run('remove', 'all') == 'Removed: all abilities.'
