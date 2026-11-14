"""Rebuild LCUItemBridge from current sources and pin the exact DLL in a manifest.

Run with the repository's 64-bit Windows Python. Never overwrites an old DLL;
restarts are necessary because the running client holds its selected path.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'worlds/lego_city_undercover/bridge'))
from native_build_integrity import source_digest, bridge_health
from patch_native_cheat_bridge import apply_patch as patch_cheat_grant


def rebuild(root=ROOT, python=sys.executable):
    root = Path(root).resolve()
    build = root / 'build/lego_city_undercover'
    build.mkdir(parents=True, exist_ok=True)
    if patch_cheat_grant(root):
        print('Native cheat grant: reviewed source fix installed; original saved in build/.', flush=True)
    digest_before = source_digest(root)
    filename = 'LCUItemBridgeTests_' + digest_before[:16] + '.dll'
    output = build / filename
    print('LCU Native Bridge: building', filename, flush=True)
    builder = root / 'worlds/lego_city_undercover/tools/build_item_bridge.py'
    subprocess.run([str(python), str(builder), '--output', str(output)], cwd=root, check=True)
    if source_digest(root) != digest_before:
        raise RuntimeError('Source files changed during DLL build. Restart build.')
    if output.stat().st_size < 1024 or output.read_bytes()[:2] != b'MZ':
        raise RuntimeError('Builder returned an invalid PE/DLL output.')
    manifest_path = build / 'native_items_build.json'
    try:
        prior = json.loads(manifest_path.read_text(encoding='utf-8'))
        if not isinstance(prior, dict):
            prior = {}
    except (OSError, ValueError):
        prior = {}
    prior.update(dll_filename=filename, source_digest=digest_before,
                 dll_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
    tmp = manifest_path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(prior, indent=2, sort_keys=True), encoding='utf-8')
    tmp.replace(manifest_path)
    problem = bridge_health(root)
    if problem:
        raise RuntimeError('Bridge verification failed after build: ' + problem)
    print('OK: verified', output, flush=True)
    print('Close/restart the GUI client before using new native test commands.', flush=True)
    return output


if __name__ == '__main__':
    try:
        rebuild()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
