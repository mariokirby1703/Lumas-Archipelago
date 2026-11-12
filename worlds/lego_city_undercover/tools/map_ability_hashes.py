"""Reproduce symbol-name associations from a local live read and the local executable."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
from research_profile import symbol_hash, validate_table


def main() -> None:
    world = Path(__file__).resolve().parents[1]
    analysis = world / "notes/analysis"
    snapshot = json.loads((analysis / "live_main_menu.json").read_text(encoding="utf-8-sig"))
    values = snapshot["processes"][0]["research_state"]["ability_hash_table"]
    validate_table(values)
    names: dict[int, set[str]] = {}
    for match in re.finditer(rb"[\x20-\x7e]{2,}", (world / "notes/gamefiles/LEGOLCUR_DX11.exe").read_bytes()):
        name = match.group().decode("ascii")
        value = symbol_hash(name)
        if value in values:
            names.setdefault(values.index(value), set()).add(name)
    rows = [dict(index=index, hash=value, names=sorted(names.get(index, set())))
            for index, value in enumerate(values)]
    (analysis / "ability_hash_mapping.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"Matched names for {sum(bool(row['names']) for row in rows)} of {len(values)} runtime symbols.")


if __name__ == "__main__":
    main()
