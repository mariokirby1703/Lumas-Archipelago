"""Generate research candidates, never active AP locations, from extracted tables."""
from __future__ import annotations

import hashlib
import collections
import json
import re
from pathlib import Path


def parse_missions(text: str) -> list[dict[str, str]]:
    text = re.sub(r"//[^\n]*", "", text)
    result = []
    for block in re.findall(r"START_SIDE_MISSION\s+(.*?)END_SIDE_MISSION", text, re.S):
        row = dict(re.findall(r'^\s*(\w+)\s+"([^"\r\n]*)"', block, re.M))
        if not row.get("Name"):
            raise ValueError("Mission without an internal name")
        result.append(row)
    if len({row["Name"] for row in result}) != len(result):
        raise ValueError("Duplicate mission names")
    return result


def parse_objectives(text: str) -> list[dict[str, str]]:
    text = re.sub(r"//[^\n]*", "", text)
    result = []
    for block in re.findall(r"info_start\s+(.*?)info_end", text, re.S):
        row = dict(re.findall(r'^\s*(\w+)\s+"([^"\r\n]*)"', block, re.M))
        if not row.get("instanceName") or not row.get("objectiveTypeId"):
            raise ValueError("Objective without an instance name/type")
        result.append(row)
    return result


def main() -> None:
    world = Path(__file__).resolve().parents[1]
    extracted = world / "notes/extracted/GAME7"
    rows = []
    lines = ["# Collectible mapping", "", "Static candidates, not runtime-detectable AP checks.",
             "No persistent completion offsets, ability requirements, or district display-name mappings are verified.", "",
             "| Source table | Definitions | Evidence |", "|---|---:|---|"]
    for source in sorted((extracted / "stuff/sidemissions").glob("*.txt")):
        content = source.read_bytes()
        missions = parse_missions(content.decode("utf-8-sig"))
        relative = source.relative_to(extracted).as_posix()
        digest = hashlib.sha256(content).hexdigest()
        lines.append(f"| `{relative}` | {len(missions)} | SHA-256 `{digest}` |")
        for mission in missions:
            rows.append(dict(source_archive="GAME7.DAT", source_path=relative, source_sha256=digest,
                             definition=mission, evidence="static table", persistent_flag=None,
                             enabled_as_ap_location=False))
    if not rows:
        raise FileNotFoundError("Extract stuff/sidemissions first")
    output = world / "notes/analysis/candidate_missions.json"
    output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines += ["", "TimeTrials contains 60 definitions; this does not establish 60 active, independent checks.",
              "VehicleTheft entries use Type=Time Trial; category must preserve the source table.",
              "Full internal names and rewards remain in ignored notes/analysis/candidate_missions.json.",
              "The scanner table separately defines four shield-piece pickup types; persistence is unverified."]
    source = extracted / "stuff/scanner/scanner_objectives.txt"
    content = source.read_bytes()
    objectives = parse_objectives(content.decode("utf-8-sig"))
    digest = hashlib.sha256(content).hexdigest()
    objective_rows = [dict(source_archive="GAME7.DAT", source_path="stuff/scanner/scanner_objectives.txt",
                           source_sha256=digest, definition=row, evidence="static table",
                           persistent_flag=None, enabled_as_ap_location=False) for row in objectives]
    (world / "notes/analysis/candidate_objectives.json").write_text(
        json.dumps(objective_rows, indent=2), encoding="utf-8")
    lines += ["", f"Scanner objective table: {len(objectives)} rows, SHA-256 `{digest}`.",
              "Declared scanner locks are candidate requirements, not a complete reachability proof.",
              "", "| Internal objective type | Rows |", "|---|---:|"]
    for name, count in sorted(collections.Counter(row["objectiveTypeId"] for row in objectives).items()):
        lines.append(f"| `{name}` | {count} |")
    lines += ["", "| Internal district | Rows |", "|---|---:|"]
    for name, count in sorted(collections.Counter(row.get("cityDistrict", "unspecified")
                                                for row in objectives).items()):
        lines.append(f"| `{name}` | {count} |")
    (world / "docs/research/collectible_mapping.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Recorded {len(rows)} mission and {len(objectives)} scanner rows; zero enabled AP locations.")


if __name__ == "__main__":
    main()
