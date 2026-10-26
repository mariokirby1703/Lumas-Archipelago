"""Routine logs are command-visible, never spam the normal Sonic GUI."""
import ast
import importlib.util
from pathlib import Path


CLIENT = Path(__file__).resolve().parents[1] / 'client'


def module():
    path = CLIENT / 'quiet_logging.py'
    spec = importlib.util.spec_from_file_location('sonic_quiet_logging_test', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_ring_buffer_and_command_read_are_bounded():
    q = module()
    for i in range(520):
        q.record('pickup', 'Captured check %s', i)
    assert q.history()['stored'] == 500
    assert q.history(3)['entries'][0]['message'] == 'Captured check 517'
    assert len(q.history(None)['entries']) == 500
    assert q.clear() == 500
    assert q.history()['entries'] == []


def test_same_event_is_coalesced_without_loss():
    q = module()
    q.record('stage', 'Act %s loaded', 1)
    q.record('stage', 'Act %s loaded', 1)
    assert q.history()['stored'] == 1
    assert q.history()['entries'][0]['repeats'] == 2
    q.record('stage', 'Act %s loaded', 2)
    assert q.history()['stored'] == 2


def _function(tree, name):
    return next(n for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def _calls(function, root, method):
    return [node for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == method
            and isinstance(node.func.value, ast.Name) and node.func.value.id == root]


def test_native_and_network_automatic_messages_are_not_printed():
    client = ast.parse((CLIENT / 'client.py').read_text())
    runtime = ast.parse((CLIENT / 'runtime.py').read_text())
    medals = ast.parse((CLIENT / 'medal_hook.py').read_text())
    for name in ('on_package', 'transmit_checks', 'dolphin_loop'):
        assert not _calls(_function(client, name), 'logger', 'info')
    for name in ('observe_pickups', 'observe_capsules', 'observe_results',
                 'apply_effects', 'settle_effects', 'select_resource_music'):
        assert not _calls(_function(runtime, name), 'logger', 'info')
    assert not _calls(_function(medals, 'observe'), 'logger', 'info')
    assert _calls(_function(client, 'dolphin_loop'), 'quiet_logging', 'record')
    assert _calls(_function(client, 'on_package'), 'quiet_logging', 'record')


def test_commands_still_print_when_requested():
    tree = ast.parse((CLIENT / 'client.py').read_text())
    for cmd in ('_cmd_soniclogs', '_cmd_sonicstatus', '_cmd_sonicdebug',
                '_cmd_sonicmovement', '_cmd_sonicitems'):
        assert _function(tree, cmd)
    assert _calls(_function(tree, '_cmd_soniclogs'), 'quiet_logging', 'history')
    assert _calls(_function(tree, '_cmd_soniclogs'), 'quiet_logging', 'clear')
    assert _calls(_function(tree, 'log_diagnostic'), 'logger', 'info')


def test_critical_synchronization_errors_stay_visible():
    tree = ast.parse((CLIENT / 'client.py').read_text())
    assert _calls(_function(tree, 'on_package'), 'logger', 'error')
    runtime = ast.parse((CLIENT / 'runtime.py').read_text())
    assert _calls(_function(runtime, 'settle_effects'), 'logger', 'warning')


def test_live_command_handler_shows_logs_and_clear_only_on_request():
    """Run the actual extracted command body without importing AP Core."""
    import types
    tree = ast.parse((CLIENT / 'client.py').read_text())
    command = _function(tree, '_cmd_soniclogs')
    command.decorator_list = []
    mod = ast.fix_missing_locations(ast.Module(body=[command], type_ignores=[]))
    q = module()
    outputs = []
    sink = types.SimpleNamespace(info=lambda fmt, *args: outputs.append(fmt % args if args else fmt))
    scope = {'quiet_logging': q, 'logger': sink,
             'log_diagnostic': lambda value: outputs.append(value)}
    exec(compile(mod, '<extracted_soniclogs>', 'exec'), scope)
    handler = scope['_cmd_soniclogs']
    assert outputs == []
    q.record('pickup', 'Ring %s', 1)
    q.record('pickup', 'Ring %s', 2)
    assert outputs == []  # suppressed routine output
    handler(None, '1')
    assert outputs[-1]['showing'] == 1
    assert outputs[-1]['entries'][0]['message'] == 'Ring 2'
    handler(None, 'all')
    assert outputs[-1]['showing'] == 2
    handler(None, 'clear')
    assert q.history()['stored'] == 0
    assert outputs[-1] == 'Cleared 2 stored Sonic diagnostic log entries.'
    handler(None, 'abc')
    assert 'Usage: /soniclogs' in outputs[-1]
