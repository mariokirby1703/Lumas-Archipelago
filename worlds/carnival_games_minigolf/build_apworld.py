"""Build a deterministic, self-contained APWorld archive using only the standard library.

Run from any directory: python worlds/carnival_games_minigolf/build_apworld.py
Optional: --output PATH --install CUSTOM_WORLDS_DIRECTORY
"""
import argparse
import ast
import hashlib
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


def build(output):
    source = Path(__file__).resolve().parent
    manifest = json.loads((source / 'archipelago.json').read_text(encoding='utf-8'))
    assert manifest['game'] == 'Carnival Games MiniGolf'
    required = ('__init__.py', 'world.py', 'Options.py', 'Items.py', 'Locations.py', 'Regions.py',
                'Rules.py', 'components.py', 'data.py', 'client/client.py', 'client/runtime.py',
                'client/memory.py', 'client/constants.py', 'client/journal.py', 'client/launch.py',
                'docs/setup_en.md', 'requirements.txt', 'archipelago.json')
    for name in required:
        if not (source / name).is_file():
            raise FileNotFoundError(name)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob('*')):
            relative = path.relative_to(source)
            if not path.is_file() or any(part in {'notes', 'test', '__pycache__', '.pytest_cache'} for part in relative.parts):
                continue
            if path.suffix not in {'.py', '.md', '.json', '.txt', '.yaml', '.png', '.svg'}:
                continue
            content = path.read_bytes()
            if relative.as_posix() == 'archipelago.json':
                content = json.dumps({**manifest, 'version': 7, 'compatible_version': 7}, indent=2).encode('utf-8')
            if path.suffix == '.py':
                ast.parse(content, filename=str(relative))
            info = zipfile.ZipInfo(f'{source.name}/{relative.as_posix()}', (2026, 9, 14, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise ValueError('APWorld archive integrity check failed')
    temporary.replace(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[2] /
                        'build/apworlds/carnival_games_minigolf.apworld')
    parser.add_argument('--install', type=Path, help='Existing Archipelago custom_worlds folder')
    args = parser.parse_args()
    output = build(args.output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    print(f'Built: {output}\nSHA-256: {digest}')
    if args.install:
        destination_dir = args.install.resolve(strict=True)
        if not destination_dir.is_dir() or destination_dir.name != 'custom_worlds':
            parser.error('--install must name an existing custom_worlds directory')
        destination = destination_dir / output.name
        if destination.exists():
            backup = destination.with_suffix('.apworld.' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.bak')
            shutil.copy2(destination, backup)
        shutil.copy2(output, destination)
        assert hashlib.sha256(destination.read_bytes()).hexdigest() == digest
        print(f'Installed: {destination}')


if __name__ == '__main__':
    main()
