"""Identify the loaded Sonic implementation independently of AP's version.

The code ID hashes actual loaded code objects. A packaged commit is attribution
from the build manifest, not a guess based on the surrounding checkout's HEAD.
"""
import hashlib
import json
import marshal
import subprocess
from functools import lru_cache
from pathlib import Path
from importlib.resources import files


@lru_cache(maxsize=1)
def implementation_info():
    from .hooks import NativeHooks
    from .runtime import Runtime, detect_checks
    from .state import SaveGuard, WritePolicy
    from .memory import SonicMemory, DMEBackend
    from .gecko import inspect_c2, branch_target
    from . import gameplay_controls, medal_hook, music_bank, map_refresh, live_music, direct_hooks
    from .runtime import rings_amount
    from . import hooks, runtime, state, binding, native_read, client, journal, status, capsule_refresh, versions, progression_hook, music
    functions = (NativeHooks.snapshot, NativeHooks.project_permissions, NativeHooks.project_live_permissions, NativeHooks.kill,
                 NativeHooks.swim, Runtime.poll, Runtime.configure_native_hooks, Runtime.select_resource_music, Runtime.apply_effects, Runtime.effect_context, Runtime.boost_grant_context, Runtime.temporary_boost_allowed, rings_amount, detect_checks,
                 SaveGuard.observe, SaveGuard.check, SaveGuard.check_stats, WritePolicy.__call__, NativeHooks._snapshot_after_revision,
                 Runtime.observe_pickups, Runtime.observe_capsules, binding.SaveBinding.attribute,
                 native_read.read_capsules, client.SonicContext.on_package, client.transmit_checks, journal.Journal.save, journal.Journal.record_pickups, Runtime.observe_results, Runtime.settle_effects,
                 native_read.read_result, native_read.read_stage_objects, native_read.read_player,
                 status.StatusReporter.ready, capsule_refresh.payload_words,
                 capsule_refresh.installed, capsule_refresh.inspect_installed, inspect_c2, branch_target, versions.verify_revision, journal.Journal.defer,
                 SonicMemory.write_bytes_verified, SonicMemory.resolve_selected_slot, DMEBackend.assert_instance, DMEBackend.write_bytes,
                 native_read._read_stage_objects, native_read.read_saved_progress,
                 NativeHooks.reject_observation, SaveGuard.suspend, client.dolphin_loop,
                 progression_hook.payload, progression_hook.installed_data, progression_hook.configure,
                 progression_hook.events, progression_hook.identity_tag, music.cue_records, music.apply_music, music.mapping_for,
                 gameplay_controls.payload, gameplay_controls.installed, gameplay_controls.configure, capsule_refresh.configure, capsule_refresh.installed_data,
                 native_read.read_medals, medal_hook.payload, medal_hook.installed_data, medal_hook.configure, medal_hook.observe,
                 music_bank.plan, music_bank.rewrite_bank, music_bank.validate_resource_bank, music_bank.load_manifest, music_bank.patch,
                 live_music.apply, live_music.probe_bank, live_music.recover_original,
                 direct_hooks.plan, direct_hooks.install, direct_hooks.inspect, client.log_diagnostic, gameplay_controls.gecko_lines,
                 map_refresh.payload, map_refresh.installed_data, map_refresh.configure, capsule_refresh.gecko_ini)
    digest = hashlib.sha256()
    for function in functions:
        digest.update(function.__qualname__.encode())
        digest.update(marshal.dumps(function.__code__))
    result = {'loaded_code_id': digest.hexdigest(),
              'loaded_python_paths': {module.__name__: module.__file__
                                      for module in (hooks, runtime, state, binding, native_read)},
              'package_path': str(files('worlds.sonic_colours')),
              'commit': None, 'package_build_id': None}
    manifest = files('worlds.sonic_colours').joinpath('build_manifest.json')
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding='utf-8'))
        mismatches = [name for name, expected in data['files'].items()
                      if hashlib.sha256(files('worlds.sonic_colours').joinpath(name).read_bytes()).hexdigest() != expected]
        result.update(commit=data['commit'], package_build_id=data['build_id'],
                      build_dirty=data['dirty'], manifest_verified=not mismatches,
                      manifest_mismatches=mismatches)
    else:
        result['build_kind'] = 'source checkout; loaded_code_id identifies this process'
        root = Path(hooks.__file__).resolve().parents[1]
        try:
            result['commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root,
                                                       text=True, stderr=subprocess.DEVNULL).strip()
            result['build_dirty'] = bool(subprocess.check_output(
                ['git', 'status', '--porcelain', '--', '.'], cwd=root,
                text=True, stderr=subprocess.DEVNULL).strip())
        except (OSError, subprocess.CalledProcessError):
            pass
    return result
