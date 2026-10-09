"""Build a deterministic Sonic Colours APWorld without notes, binaries or RAM dumps."""
import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path
import zipfile


def build(destination):
    root = Path(__file__).resolve().parent
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    contents = {}
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(root.rglob('*')):
                relative = path.relative_to(root)
                if (not path.is_file() or any(p in {'notes', 'test', 'tools', '__pycache__', '.pytest_cache'}
                                             for p in relative.parts)
                        or relative.name == 'build_apworld.py'
                        or relative.name.startswith('live_pal_') and path.suffix == '.json'
                        or path.suffix not in {'.py', '.json', '.md', '.yaml', '.txt', '.ini'}):
                    continue
                content = path.read_bytes()
                if path.suffix == '.py':
                    ast.parse(content, filename=str(relative))
                if relative.as_posix() == 'archipelago.json':
                    content = json.dumps({**json.loads(content), 'version': 2, 'compatible_version': 2}).encode()
                info = zipfile.ZipInfo(f'sonic_colours/{relative.as_posix()}', (2026, 10, 9, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, content)
                if path.suffix in {'.py', '.json', '.ini'}:
                    contents[relative.as_posix()] = hashlib.sha256(content).hexdigest()
            # Include provenance in the artifact itself. Dirty builds are explicit
            # and receive a content ID; HEAD alone must never imply identical code.
            try:
                commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root,
                                                 text=True, stderr=subprocess.DEVNULL).strip()
                dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--', '.'],
                                                     cwd=root, text=True, stderr=subprocess.DEVNULL).strip())
            except (OSError, subprocess.CalledProcessError):
                commit, dirty = None, None
            manifest = {'commit': commit, 'dirty': dirty, 'files': contents,
                        'build_id': hashlib.sha256(json.dumps(contents, sort_keys=True).encode()).hexdigest()}
            info = zipfile.ZipInfo('sonic_colours/build_manifest.json', (2026, 10, 9, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, json.dumps(manifest, sort_keys=True))
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip():
                raise ValueError('archive integrity failure')
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[2] /
                        'build/apworlds/sonic_colours.apworld')
    args = parser.parse_args()
    path = build(args.output)
    print(f'{path}\nSHA256: {hashlib.sha256(path.read_bytes()).hexdigest()}')
