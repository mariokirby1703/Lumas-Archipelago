"""Reproduce local research, test it, and build the standalone diagnostic archive.

No step launches the game, writes game memory or edits saves.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-inventory", action="store_true", help="Reuse earlier hashes; do not rehash original files")
    parser.add_argument("--with-disassembly", action="store_true", help="Requires installed capstone")
    args = parser.parse_args()
    world = Path(__file__).resolve().parents[1]
    tools = world / "tools"
    stages = ([] if args.skip_inventory else ["inspect_game.py"]) + [
        "archive_index.py", "harvest_research.py", "collection_data.py", "map_candidates.py", "job_data.py",
        "script_catalogue.py", "resource_catalogue.py", "pickup_catalogue.py",
    ]
    if args.with_disassembly:
        stages.append("action_xrefs.py")
    for stage in stages:
        print(f"Running {stage}", flush=True)
        subprocess.run([sys.executable, str(tools / stage)], check=True)
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(world / "tests"), "-v"], check=True)
    subprocess.run([sys.executable, str(tools / "build_diagnostics.py")], check=True)
    analysis = world / "notes/analysis"
    names = ("inventory.json", "archive_summary.json", "extracted_manifest.json", "job_data_summary.json",
             "script_catalogue_summary.json", "gizmo_summary.json")
    report = dict(stages=stages, inventory_refreshed=not args.skip_inventory, tests_passed=True,
                  gameplay_validated=False,
                  reports={name: hashlib.sha256((analysis / name).read_bytes()).hexdigest() for name in names})
    (analysis / "pipeline_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Research pipeline and diagnostic build passed. Gameplay remains unverified.")


if __name__ == "__main__":
    main()
