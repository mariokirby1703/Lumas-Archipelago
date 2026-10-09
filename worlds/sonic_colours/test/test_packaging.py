import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from ..build_apworld import build


def test_apworld_has_verifiable_build_identity_without_private_assets(tmp_path):
    first = build(tmp_path / 'one.apworld')
    second = build(tmp_path / 'two.apworld')
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        manifest = json.loads(archive.read('sonic_colours/build_manifest.json'))
        assert manifest['commit'] and len(manifest['commit']) == 40
        assert manifest['build_id'] == hashlib.sha256(
            json.dumps(manifest['files'], sort_keys=True).encode()).hexdigest()
        for name, digest in manifest['files'].items():
            assert hashlib.sha256(archive.read('sonic_colours/' + name)).hexdigest() == digest
        assert not any('/notes/' in name or name.endswith(('.dol', '.cpk', '.raw'))
                       for name in archive.namelist())


def test_launcher_world_loader_prefers_checkout_over_both_installed_copies(tmp_path):
    custom = tmp_path / 'worlds'
    stale = custom / 'sonic_colours'
    stale.mkdir(parents=True)
    (stale / '__init__.py').write_text("raise RuntimeError('STALE CLIENT LOADED')\n")
    (custom / 'sonic_colours.apworld').write_bytes(b'not a valid zip; must be ignored')
    script = '''
import unittest
import sys
from pathlib import Path
import Utils
custom = Path(sys.argv[1])
Utils.user_path = lambda *parts: str(custom.joinpath(*parts))
import worlds
from worlds.sonic_colours.client import hooks
assert not any(s.name == 'sonic_colours' and not s.relative for s in worlds.world_sources)
print(Path(hooks.__file__).resolve())
'''
    root = Path(__file__).resolve().parents[3]
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path)], cwd=root,
                            env={**os.environ, 'AP_TEST_WORLDS': 'sonic_colours',
                                 'SKIP_REQUIREMENTS_UPDATE': '1'},
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert str(root / 'worlds/sonic_colours/client/hooks.py') in result.stdout
