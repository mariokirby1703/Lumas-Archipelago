"""Identify the exact locally built native bridge without loading the DLL."""
import hashlib
import json
from pathlib import Path


def build_sources(root):
    root = Path(root)
    bridge = root / 'worlds/lego_city_undercover/bridge'
    native = bridge / 'native'
    files = [native / 'item_bridge.cpp',
             *sorted(native.glob('*.h')),
             bridge / 'purchase_gate.py',
             bridge / 'model_selection.py',
             bridge / 'category_selection.py',
             bridge / 'native_context_policy.py',
             root / 'worlds/lego_city_undercover/tools/build_item_bridge.py']
    missing = [path for path in files if not path.is_file()]
    if missing:
        raise ValueError('Native Bridge-Quelldatei fehlt: ' + str(missing[0]))
    return files


def source_digest(root):
    root = Path(root).resolve()
    sha = hashlib.sha256()
    for path in build_sources(root):
        sha.update(path.relative_to(root).as_posix().encode('utf-8'))
        sha.update(b'\0')
        sha.update(path.read_bytes())
        sha.update(b'\0')
    return sha.hexdigest()


def bridge_health(root):
    """Return reason on missing/unverified/obsolete build; otherwise None."""
    root = Path(root)
    directory = root / 'build/lego_city_undercover'
    manifest = directory / 'native_items_build.json'
    try:
        data = json.loads(manifest.read_text(encoding='utf-8'))
        filename = data.get('dll_filename')
        if (not isinstance(filename, str) or Path(filename).name != filename or
                not filename.startswith('LCUItemBridge') or not filename.endswith('.dll')):
            return 'Native-Build-Manifest hat keinen gültigen DLL-Namen.'
        dll = directory / filename
        if not dll.is_file():
            return 'Die eingetragene Native-DLL existiert nicht: ' + str(dll)
        actual = source_digest(root)
        if data.get('source_digest') != actual:
            return ('Native-DLL ist nicht nachweislich aus den aktuellen Quellen gebaut. '
                    'Bitte RebuildLCUNativeBridge.cmd ausführen.')
        expected = data.get('dll_sha256')
        if expected != hashlib.sha256(dll.read_bytes()).hexdigest():
            return 'Native-DLL-Hash stimmt nicht mit dem Build-Manifest überein. Bitte neu bauen.'
        return None
    except (OSError, ValueError, TypeError) as error:
        return 'Native-DLL konnte nicht geprüft werden: ' + str(error) + '. Bitte neu bauen.'
