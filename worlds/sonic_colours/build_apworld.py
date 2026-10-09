"""Build a deterministic research APWorld without notes, binaries or RAM dumps."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import zipfile


def build(destination):
    root = Path(__file__).resolve().parent
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(root.rglob('*')):
                relative = path.relative_to(root)
                if (not path.is_file() or any(p in {'notes', 'test', 'tools', '__pycache__', '.pytest_cache'}
                                             for p in relative.parts)
                        or relative.name == 'build_apworld.py'
                        or path.suffix not in {'.py', '.json', '.md', '.yaml', '.txt'}):
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
