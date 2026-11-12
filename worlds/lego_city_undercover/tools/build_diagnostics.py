"""Build a reproducible, asset-free standalone Python diagnostic archive.

This is not LegoCityUndercoverAPClient.exe and does not connect to Archipelago.
The resulting .pyz requires 64-bit Python 3.11+ on Windows and has no third-party dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

SOURCES = ("diagnose.py", "objective_reader.py", "research_profile.py", "inventory_reader.py", "collection_manifest.json",
           "actor_reader.py", "story_reader.py")


def build(world: Path, target: Path) -> str:
    files = {name: (world / "bridge" / name).read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
             for name in SOURCES}
    files["__main__.py"] = b'import runpy\nrunpy.run_module("diagnose", run_name="__main__")\n'
    manifest = dict(kind="read-only research diagnostics", format_version=1, gameplay_supported=False,
                    files={name: hashlib.sha256(content).hexdigest() for name, content in sorted(files.items())})
    files["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)
    with zipfile.ZipFile(temporary) as archive:
        if set(archive.namelist()) != set(SOURCES) | {"__main__.py", "manifest.json"}:
            raise ValueError("Unexpected diagnostic package contents")
        if archive.testzip() is not None:
            raise ValueError("Diagnostic ZIP verification failed")
    temporary.replace(target)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def main() -> None:
    world = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=world.parents[1] / "build/lego_city_undercover/LegoCityUndercoverDiagnostics.pyz")
    args = parser.parse_args()
    digest = build(world, args.output)
    print(json.dumps(dict(path=str(args.output.resolve()), sha256=digest, kind="read-only diagnostics"), indent=2))


if __name__ == "__main__":
    main()
