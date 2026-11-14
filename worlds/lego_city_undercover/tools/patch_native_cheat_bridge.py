"""Safely patch exactly the supported LCU cheat-grant source before a DLL rebuild.

No Windows process is opened here. The original source is backed up in ignored
build/; a changed/unrecognized source fails closed rather than guessing offsets.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path('worlds/lego_city_undercover/bridge/native/item_bridge.cpp')
# Blob SHA from the actual a871e86 branch, not an executable hash.
PINNED_GIT_BLOB = '514e9e8a567b5fc9e4089135494efb4ae7332f3a'
MARKER = 'LCU_CHEAT_SERIALIZED_OWNERSHIP_V1'

OLD = '''            const unsigned char prefix[]={0x57,0x48,0x83,0xec,0x50};
            if(std::memcmp(reinterpret_cast<void*>(base+0x7f19a0),prefix,sizeof(prefix)))return 1;
            if(!(*effect&mask)) {
                // edx=0 skips the original pickup's mission/reward bookkeeping.
                using Unlock=void(*)(int,int,bool);
                reinterpret_cast<Unlock>(base+0x7f19a0)(c->model,0,false);
            }
'''
NEW = '''            // LCU_CHEAT_SERIALIZED_OWNERSHIP_V1
            // 0x7f19a0 is not callable using the pinned prologue: the live
            // signature check rejects it. Instead, modify ONLY the already
            // verified serialized cheat-ownership mask, never the native
            // Red Brick discovery flags, story or runtime activation bytes.
            // The source reader/save verifier use the same exact layout.
            auto profile=*reinterpret_cast<std::uintptr_t*>(base+0x1c7f160);
            if(!profile || count!=40 ||
               reinterpret_cast<std::uintptr_t>(found)!=profile+0xfa70 ||
               reinterpret_cast<std::uintptr_t>(effect)!=profile+0xfa80)return 5;
            const auto found_before=*found;
            *effect|=mask;
            // Preserve the genuine Red Brick source-discovery bank verbatim.
            if(*found!=found_before)return 7;
'''


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


def apply_patch(root: Path = ROOT) -> bool:
    root = Path(root).resolve()
    path = root / SOURCE
    data = path.read_bytes()
    # Rebuilds can run repeatedly; never reapply to the same source.
    if MARKER.encode('ascii') in data:
        if data.count(MARKER.encode('ascii')) != 1 or OLD.encode('utf-8') in data:
            raise ValueError('Native-Cheat-Patch ist uneindeutig. Datei manuell prüfen: ' + str(path))
        return False
    if git_blob_sha(data) != PINNED_GIT_BLOB:
        raise ValueError('Native C++ source differs from the reviewed a871e86 commit. '
                         'No patch applied. Review changes manually; do NOT disable signature guards.')
    text = data.decode('utf-8')
    if text.count(OLD) != 1:
        raise ValueError('The original native cheat grant code was not found exactly once.')
    changed = text.replace(OLD, NEW).encode('utf-8')
    backup = root / 'build/lego_city_undercover/item_bridge_before_cheat_fix.cpp'
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists() and backup.read_bytes() != data:
        raise ValueError('An existing native source backup differs. Refusing to overwrite.')
    if not backup.exists():
        backup.write_bytes(data)
    path.write_bytes(changed)
    return True


if __name__ == '__main__':
    try:
        changed = apply_patch()
        print('Native cheat source: ' + ('patched (original backed up)' if changed else 'already patched'))
    except (OSError, ValueError) as exc:
        print('ERROR:', exc)
        raise SystemExit(1)
