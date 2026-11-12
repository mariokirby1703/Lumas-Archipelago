"""Reproduce the targeted local research extraction without overwriting files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from archive_index import extract, read_index, safe_target


def wanted(name: str) -> bool:
    return (name == "levels\\levels.txt" or name in ("stuff\\gameversion.txt", "chars\\abilities.txt",
                                                    "chars\\collection.txt", "chars\\characterorder.txt", "chars\\chardata.txt")
            or name.startswith("chars\\minifigs\\cop\\cop_female_p2\\") and name.endswith(".txt")
            or name.startswith(("stuff\\scanner\\", "stuff\\sidemissions\\", "stuff\\citydistricts\\",
                                "stuff\\missions\\", "abilities\\", "jobs\\"))
            or name.endswith((".cpj", ".giz"))
            or (name.endswith(".sf") and any(token in name for token in (
                "forceunlocks", "audioscanunlock", "police_station_getdisguise", "unlockparkour", "lockunlocksetup"))))


def main() -> None:
    world = Path(__file__).resolve().parents[1]
    manifest = []
    for archive in sorted((world / "notes/gamefiles").glob("*.DAT")):
        for entry in read_index(archive):
            name = entry["path"]
            if not name or not wanted(name):
                continue
            data = extract(archive, entry)
            target = safe_target(world / "notes/extracted" / archive.stem, name)
            if target.exists():
                if target.read_bytes() != data:
                    raise ValueError(f"Existing extraction differs: {target}")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(data)
            manifest.append(dict(archive=archive.name, path=name, size=len(data),
                                 sha256=hashlib.sha256(data).hexdigest()))
    output = world / "notes/analysis/extracted_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Validated {len(manifest)} extracted files, {sum(row['size'] for row in manifest)} bytes.")


if __name__ == "__main__":
    main()
