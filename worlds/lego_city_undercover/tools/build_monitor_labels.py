"""Generate factual event labels from local tables, without packaging source assets."""
import json
from pathlib import Path
import sys

WORLD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORLD / "bridge"))
from research_profile import symbol_hash


def main():
    objectives = json.loads((WORLD / "notes/analysis/candidate_objectives.json").read_text())
    labels = {}
    for row in objectives:
        d = row["definition"]
        key = str(symbol_hash(d["instanceName"]))
        entry = {k: d.get(k, "") for k in ("instanceName", "objectiveTypeId", "cityDistrict")}
        if key in labels and labels[key] != entry:
            labels[key] = None
        elif key not in labels:
            labels[key] = entry
    # These mappings come from isolated or user-confirmed live collection observations.
    observed = {
        2490: ("wi_farmlands_0708.giz", 36, "j_pup"),
        2488: ("wi_farmlands_0708.giz", 34, "Diner_2x2_01_PU"),
        2489: ("wi_farmlands_0708.giz", 35, "Diner_2x2_02_PU"),
        2491: ("wi_farmlands_0708.giz", 37, "Brickup_01"),
        7072: ("sf_residential_1023_tech.giz", 0, "Icebox_Brick"),
        968: ("wi_forest_0703.giz", 0, "P_pup"),
    }
    output = dict(objectives=labels, superbricks={str(k): dict(resource=v[0], index=v[1], name=v[2])
                                                for k,v in observed.items()})
    output['models']={str(k):dict(display_name=name,evidence='user-confirmed display name') for k,name in
                      ((387,'Sam Penn'),(704,'Rob Shepherd'),(409,'Häftling'))}
    native_file=WORLD/'bridge/city_pickup_bindings.json'
    if native_file.exists():
        for bit,row in json.loads(native_file.read_text()).items():
            output['superbricks'][bit]=dict(resource=row['resource'],name=row['name'],
                                           source_key=row['source_key'],evidence=row['evidence'])
    (WORLD / "bridge/monitor_labels.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(labels)} objective labels, {len(output['superbricks'])} supported Super Brick mappings")


if __name__ == "__main__":
    main()
