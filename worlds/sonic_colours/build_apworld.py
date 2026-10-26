"""Build a deterministic Sonic Colours APWorld without notes, binaries or RAM dumps."""
import argparse
import ast
import hashlib
import json
import subprocess
from pathlib import Path
import zipfile

CANONICAL_DOCS = {'sonic_colours.md', 'setup.md'}
# WebHostLib.misc.game_info uses secure_filename(game), regardless of Tutorials.
WEB_GAME_INFO = 'en_Sonic_Colours_Wii.md'
PATCH_TOOLS = {'__init__.py','build_hud_overlay.py','hud_cpk.py','hud_gncp.py',
               'hud_original_assets.py','hud_preflight.py','hud_tpl.py'}
PUBLIC_EXAMPLES = {'SonicColours.yaml', 'SonicColours_Template.yaml'}
EXCLUDED_PARTS = {'notes','test','__pycache__','.pytest_cache','.mypy_cache',
                  '.ruff_cache','build','.git'}


def release_file(relative):
    """Explicit release boundary; preserve all runtime/data files locally."""
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if relative.suffix not in {'.py','.json','.md','.yaml','.txt','.csv','.png'}:
        return False
    if len(relative.parts)==1:
        return (relative.suffix=='.py' and relative.name!='build_apworld.py'
                or relative.name in {'archipelago.json','README.md','requirements.txt'})
    directory=relative.parts[0]
    if directory=='docs':
        return len(relative.parts)==2 and relative.name in CANONICAL_DOCS
    if directory=='tools':
        return len(relative.parts)==2 and relative.name in PATCH_TOOLS
    if directory=='examples':
        return len(relative.parts)==2 and relative.name in PUBLIC_EXAMPLES
    return directory in {'client','data','assets'}


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
                if not path.is_file() or not release_file(relative):
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
                contents[relative.as_posix()] = hashlib.sha256(content).hexdigest()
            # Source has two maintained guides. Stock WebHost requires this
            # third filename for /games/Sonic Colours (Wii)/info/en.
            overview=(root/'docs/sonic_colours.md').read_bytes()
            alias='docs/'+WEB_GAME_INFO
            info=zipfile.ZipInfo('sonic_colours/'+alias,(2026,10,9,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644<<16
            archive.writestr(info,overview)
            contents[alias]=hashlib.sha256(overview).hexdigest()
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
