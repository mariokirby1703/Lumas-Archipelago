"""Read-only copy of a stable save-slot directory into ignored local research storage.

Does not modify or restore the original save. File-format validity is not implied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time


def backup_slot(source: Path, destination: Path) -> dict:
    source = source.resolve(strict=True)
    if not source.is_dir() or destination.exists():
        raise ValueError("Expected a source directory and a new backup directory")
    paths = sorted(path for path in source.rglob("*") if path.is_file())
    if not paths:
        raise ValueError("Save-slot directory is empty")
    if sum(path.stat().st_size for path in paths) > 64 * 1024 * 1024:
        raise ValueError("Slot exceeds research backup limit")
    captured = {}
    for path in paths:
        if not path.resolve().is_relative_to(source):
            raise ValueError("Save-slot link escapes its directory")
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
            raise RuntimeError("Save changed during capture; retry after saving finishes")
        captured[path] = (data, after.st_mtime_ns)
    # Recheck the whole set before writing the backup: catch cross-file autosave updates.
    if sorted(path for path in source.rglob("*") if path.is_file()) != paths:
        raise RuntimeError("Save file set changed during capture")
    for path, (data, stamp) in captured.items():
        if path.stat().st_mtime_ns != stamp or path.read_bytes() != data:
            raise RuntimeError("Save changed during verification")
    manifest = dict(source=str(source), format_validated=False, stable_double_read=True, files=[])
    destination.mkdir(parents=True, exist_ok=False)
    for path, (data, stamp) in captured.items():
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
        digest = hashlib.sha256(data).hexdigest()
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Backup verification failed")
        manifest["files"].append(dict(path=relative.as_posix(), size=len(data), sha256=digest))
    (destination / "backup_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    world = Path(__file__).resolve().parents[1]
    target = world / "notes/save_backups" / f"{args.source.name}_{time.time_ns()}"
    result = backup_slot(args.source, target)
    print(json.dumps(dict(backup=str(target.resolve()), files=result["files"], source_modified=False), indent=2))


if __name__ == "__main__":
    main()
