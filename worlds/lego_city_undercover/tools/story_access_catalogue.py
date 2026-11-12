"""Index literal story entry points and side effects for open-city research.

This is file-local evidence, not a control-flow graph or an executable patch.
"""
import json
from pathlib import Path
import re

HOTSPOT = re.compile(r'\bHotSpot\s+(\w+)\s*\(\s*"([^"]+)"', re.I)
EFFECT = re.compile(r'\b(?:UnlockAbility|UnlockCharacterDebug|UnlockVehicleGroup|ManageItem|CommitCollectables|TriggerAutoSave|CityResume_\w+|PlayCutscene|SetMessage)\s*\(|\.\s*(?:SetValue|SetActive|EnableNetwork|Toggle)\s*\(')


def main():
    world = Path(__file__).resolve().parents[1]
    root = world / "notes/extracted/GAME4/jobs/scripts"
    targets = ("get_grapple_gun/goto_forest.sf", "road_block_removal/road_block_removal.sf",
               "debuguse/unlocks/forceunlocks.sf")
    rows = []
    for relative in targets:
        lines = (root / relative).read_text(encoding="utf-8-sig").splitlines()
        state = None
        evidence = []
        for number, line in enumerate(lines, 1):
            code = line.split("//", 1)[0].strip()
            match = re.match(r"(?:State|Function)\s+(\w+)\s*\(", code)
            if match:
                state = match[1]
            hotspot = HOTSPOT.search(code)
            if hotspot:
                evidence.append(dict(line=number, state=state, kind="hotspot_declaration",
                                     variable=hotspot[1], name=hotspot[2]))
            if EFFECT.search(code):
                evidence.append(dict(line=number, state=state, kind="potential_side_effect", source=code))
        rows.append(dict(resource=relative, evidence=evidence))
    output = world / "notes/analysis/story_access_evidence.json"
    output.write_text(json.dumps(dict(control_flow_verified=False, scripts=rows), indent=2), encoding="utf-8")
    print(f"Indexed {sum(len(r['evidence']) for r in rows)} evidence rows in {len(rows)} scripts")


if __name__ == "__main__":
    main()
