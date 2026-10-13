"""Regression tests for exactly one concise /give or /remove client message.

Works without Archipelago Core by extracting the production handler and using
its real LocalInventoryOverrides implementation with a minimal Items stub.
"""
import ast
from collections import Counter
import importlib.util
from pathlib import Path
import sys
import types
import pytest

ROOT = Path(__file__).resolve().parents[1]


def environment(monkeypatch):
    pkg = types.ModuleType('sonic_colours')
    pkg.__path__ = [str(ROOT)]
    clientpkg = types.ModuleType('sonic_colours.client')
    clientpkg.__path__ = [str(ROOT / 'client')]
    items = types.ModuleType('sonic_colours.Items')
    items.MOVEMENT_ITEMS = ('Wall Jump', 'Homing Attack', 'Mid-Air Boost',
                            'Double Jump', 'Stomp', 'Progressive Crouch',
                            'Swim', 'Progressive Breathing')
    items.WISP_ITEMS = ('White Boost Wisp', 'Cyan Laser Wisp', 'Progressive Yellow Drill Wisp',
                        'Orange Rocket Wisp', 'Blue Cube Wisp', 'Progressive Green Hover Wisp',
                        'Progressive Pink Spikes Wisp', 'Purple Frenzy Wisp')
    items.WORLD_ITEMS = ('Tropical Resort Shuttle', 'Sweet Mountain Shuttle',
                         'Starlight Carnival Shuttle', 'Planet Wisp Shuttle',
                         'Aquarium Park Shuttle', 'Asteroid Coaster Shuttle')
    items.EMERALDS = ('Green Chaos Emerald',)
    items.GAME_LAND_SPEED = 'Progressive Game Land Speed'
    items.RANDOM_CAPSULES = 'Random Capsules'
    items.RING_VALUES = {'Red Ring': 1}
    for name, module in [('sonic_colours', pkg), ('sonic_colours.client', clientpkg),
                         ('sonic_colours.Items', items)]:
        monkeypatch.setitem(sys.modules, name, module)
    source = ROOT / 'client' / 'test_inventory.py'
    spec = importlib.util.spec_from_file_location('sonic_colours.client.test_inventory', source)
    inv = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, inv)
    spec.loader.exec_module(inv)

    tree = ast.parse((ROOT / 'client' / 'client.py').read_text())
    classdef = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'SonicCommands')
    method = next(node for node in classdef.body if isinstance(node, ast.FunctionDef)
                  and node.name == '_change_test_ability')
    namespace = {'logger': None, 'parse_item_request': inv.parse_item_request,
                 'MAXIMUM': inv.MAXIMUM,
                 'resolve_ability_group': inv.resolve_ability_group}
    compiled = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    exec(compile(compiled, '<actual_client_command_handler>', 'exec'), namespace)

    class Capture:
        def __init__(self):
            self.messages = []
        def info(self, fmt, *args):
            self.messages.append(fmt % args if args else fmt)
        def warning(self, fmt, *args):
            self.messages.append(fmt % args if args else fmt)

    capture = Capture()
    namespace['logger'] = capture
    counts = Counter()
    for name in inv.TESTABLE:
        counts[name] = 0
    genuine = {'counts': counts, 'red_rings': 0, 'emeralds': [], 'wisps': []}
    overlay = inv.LocalInventoryOverrides()
    dummy = types.SimpleNamespace(ctx=types.SimpleNamespace(
        runtime=types.SimpleNamespace(test_inventory=overlay),refresh_movement_permissions=lambda:None),
        _test_inventory_base=lambda: genuine)

    def run(action, raw):
        before = len(capture.messages)
        namespace['_change_test_ability'](dummy, action, raw)
        lines = capture.messages[before:]
        assert len(lines) == 1, f'Expected exactly one message, got {lines!r}'
        assert '{' not in lines[0] and 'LOCAL ABILITY TEST' not in lines[0]
        return lines[0]

    return run, overlay, genuine


def test_give_remove_single_short_line(monkeypatch):
    run, overlay, genuine = environment(monkeypatch)
    assert run('give', 'laser') == 'Given: Cyan Laser Wisp.'
    assert overlay.apply(genuine)['counts']['Cyan Laser Wisp'] == 1
    assert run('remove', 'laser') == 'Removed: Cyan Laser Wisp.'
    assert overlay.apply(genuine)['counts']['Cyan Laser Wisp'] == 0
    assert run('give', 'Double Jump') == 'Given: Double Jump.'
    assert run('remove', 'Double Jump') == 'Removed: Double Jump.'


def test_progressive_level_and_no_change(monkeypatch):
    run, overlay, genuine = environment(monkeypatch)
    assert run('give', 'breath 2') == 'Given: Progressive Breathing (level 2).'
    assert overlay.apply(genuine)['counts']['Progressive Breathing'] == 2
    assert run('give', 'breath 2').startswith('No change:')
    assert run('remove', 'breath 1') == 'Removed: Progressive Breathing (level 1).'
    assert run('remove', 'breath all') == 'Removed: Progressive Breathing (level 0).'
    assert run('remove', 'breath all').startswith('No change:')


def test_all_and_errors_single_line(monkeypatch):
    run, overlay, genuine = environment(monkeypatch)
    assert run('give', 'all') == 'Given: all abilities.'
    assert run('give', 'all').startswith('No change:')
    assert run('remove', 'all') == 'Removed: all abilities.'
    assert run('remove', 'all').startswith('No change:')
    assert run('give', 'not_a_real_ability').startswith('Give failed:')
    assert run('remove', 'not_a_real_ability').startswith('Remove failed:')


def test_real_ap_receipt_remains_unchanged(monkeypatch):
    run, overlay, genuine = environment(monkeypatch)
    genuine['counts']['White Boost Wisp'] = 1
    assert run('remove', 'white') == 'Removed: White Boost Wisp.'
    assert genuine['counts']['White Boost Wisp'] == 1
    assert overlay.apply(genuine)['counts']['White Boost Wisp'] == 0
    assert run('give', 'white') == 'Given: White Boost Wisp.'
    assert overlay.apply(genuine)['counts']['White Boost Wisp'] == 1
