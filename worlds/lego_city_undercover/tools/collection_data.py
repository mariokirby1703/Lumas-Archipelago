"""Generate minimal factual roster metadata; never copy scripts or asset payloads."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


def parse_collection(text: str) -> dict:
    kind = "character"
    entries = {}
    defaults = []
    for line in text.splitlines():
        if line.strip() == ";VEHICLE_LIST_START":
            kind = "vehicle"
        code = line.split(";", 1)[0].split("//", 1)[0].strip()
        words = code.split()
        if not words:
            continue
        match = re.fullmatch(r"default\s+(?:player\s+(\d+)|(linked))\s+class\s+(\w+)\s+character\s+(\S+)", code)
        if match:
            defaults.append(dict(player=int(match[1]) if match[1] else None, linked=bool(match[2]),
                                 class_name=match[3].lower(), model=match[4].upper()))
        if words[0] != "collect":
            continue
        name = words[1].upper()
        category = int(words[words.index("cat") + 1]) if "cat" in words else None
        progress = "token" in words and "no_progress" not in words
        if name in entries:
            if entries[name]["kind"] != kind:
                raise ValueError("Model declared as both character and vehicle")
            entries[name]["counts_for_progress"] |= progress
            if category not in entries[name]["categories"]:
                entries[name]["categories"].append(category)
        else:
            entries[name] = dict(kind=kind, counts_for_progress=progress, categories=[category])
    if not entries:
        raise ValueError("No roster entries")
    for default in defaults:
        if default["model"] not in entries:
            raise ValueError("Unknown default character")
    return dict(format_version=1, entries=entries, defaults=defaults)


def main() -> None:
    world = Path(__file__).resolve().parents[1]
    raw = (world / "notes/extracted/GAME/chars/collection.txt").read_bytes()
    roster = parse_collection(raw.decode("utf-8-sig"))
    roster["source_sha256"] = hashlib.sha256(raw).hexdigest()
    target = world / "bridge/collection_manifest.json"
    target.write_text(json.dumps(roster, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print({kind: sum(row["kind"] == kind and row["counts_for_progress"] for row in roster["entries"].values())
           for kind in ("character", "vehicle")})


if __name__ == "__main__":
    main()
