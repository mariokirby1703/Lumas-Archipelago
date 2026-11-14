"""Select the built bridge without overwriting a DLL held by the game."""
import json
from pathlib import Path


def bridge_path(root):
    directory=Path(root)/'build/lego_city_undercover'
    manifest=directory/'native_items_build.json'
    filename='LCUItemBridge.dll'
    if manifest.is_file():
        filename=json.loads(manifest.read_text(encoding='utf-8')).get('dll_filename',filename)
    if not isinstance(filename,str) or Path(filename).name!=filename or not filename.startswith('LCUItemBridge') or not filename.endswith('.dll'):
        raise ValueError('Invalid native bridge artifact filename')
    return directory/filename
