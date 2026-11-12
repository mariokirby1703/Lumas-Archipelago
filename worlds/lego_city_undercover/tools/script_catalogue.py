"""Index actual script calls and possible literal arguments without executing scripts.

Variable associations are deliberately over-approximated within each source file;
they are evidence for further investigation, not control-flow or reachability proofs.
"""
from __future__ import annotations

import bisect
import collections
import hashlib
import json
from pathlib import Path
import re

TOKEN = re.compile(r'(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)|(?P<string>"(?:\\.|[^"\\])*")'
                   r'|(?P<identifier>[A-Za-z_][A-Za-z_0-9]*)|(?P<number>-?\d+(?:\.\d+)?)|(?P<symbol>[^\s])')
INTERESTING = {"CityObjective_IsComplete", "CityObjective_SetComplete", "UnlockAbility", "LockAbility",
               "IsAbilityUnlocked", "UnlockCharacterDebug", "PushExtraCharUnlockWithDisguiseSequence",
               "SetValue", "GetValue", "GivePlayerStuds", "PlayerGiveStuds", "MissionComplete",
               "CommitCollectables", "TriggerAutoSave", "Achievements_MarkChapterStart",
               "Achievements_MarkChapterComplete"}


def catalogue(text: str) -> list[dict]:
    tokens = [(match.lastgroup, match.group(), match.start()) for match in TOKEN.finditer(text)
              if match.lastgroup != "comment"]
    lines = [0] + [match.end() for match in re.finditer("\n", text)]
    literals: dict[str, set[str]] = collections.defaultdict(set)
    for index in range(len(tokens) - 2):
        kind, value, _ = tokens[index]
        if kind == "identifier" and tokens[index + 1][1] in ("=", "(") and tokens[index + 2][0] == "string":
            literals[value].add(tokens[index + 2][1][1:-1])
    calls = []
    for index, (kind, name, offset) in enumerate(tokens[:-1]):
        if kind != "identifier" or name not in INTERESTING or tokens[index + 1][1] != "(":
            continue
        arguments = []
        current = []
        depth = 0
        for token in tokens[index + 2:]:
            value = token[1]
            if value == ")" and depth == 0:
                if current:
                    arguments.append(current)
                break
            if value == "," and depth == 0:
                arguments.append(current)
                current = []
                continue
            if value == "(":
                depth += 1
            elif value == ")":
                depth -= 1
            current.append(token)
        else:
            raise ValueError(f"Unterminated {name} call")
        receiver = tokens[index - 2][1] if index >= 2 and tokens[index - 1][1] == "." else None
        args = []
        for argument in arguments:
            literal = argument[0][1][1:-1] if len(argument) == 1 and argument[0][0] == "string" else None
            hashed = "".join(token[1] for token in argument[1:]) if argument and argument[0][1] == "#" else None
            if hashed is not None and not re.fullmatch(r"[A-Za-z_0-9]+", hashed):
                hashed = None
            variable = argument[0][1] if len(argument) == 1 and argument[0][0] == "identifier" else None
            args.append(dict(expression="".join(t[1] for t in argument), literal=literal, symbol=hashed,
                             possible_literals=sorted(literals.get(variable, set())) if variable else []))
        calls.append(dict(action=name, line=bisect.bisect_right(lines, offset), receiver=receiver,
                          possible_receiver_paths=sorted(literals.get(receiver, set())), arguments=args))
    return calls


def main() -> None:
    world = Path(__file__).resolve().parents[1]
    extracted = world / "notes/extracted"
    scanner = json.loads((world / "notes/analysis/candidate_objectives.json").read_text())
    known = {row["definition"]["instanceName"] for row in scanner}
    sources = []
    objective_setters: dict[str, list[dict]] = collections.defaultdict(list)
    for path in sorted(extracted.rglob("*.sf")):
        raw = path.read_bytes()
        encoding = "utf-8-sig"
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            encoding = "cp1252"
            text = raw.decode(encoding)
        calls = catalogue(text)
        relative = path.relative_to(extracted).as_posix()
        source = dict(path=relative, sha256=hashlib.sha256(raw).hexdigest(), encoding=encoding, calls=calls)
        sources.append(source)
        for call in calls:
            if call["action"] != "CityObjective_SetComplete" or not call["arguments"]:
                continue
            arg = call["arguments"][0]
            for name in ([arg["literal"]] if arg["literal"] else arg["possible_literals"]):
                objective_setters[name].append(dict(path=relative, line=call["line"],
                    association="direct literal" if arg["literal"] else "file-local variable candidates"))
    analysis = world / "notes/analysis"
    (analysis / "script_catalogue.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
    (analysis / "objective_setter_evidence.json").write_text(json.dumps(objective_setters, indent=2), encoding="utf-8")
    counts = collections.Counter(call["action"] for source in sources for call in source["calls"])
    summary = dict(scripts=len(sources), calls=sum(counts.values()), actions=dict(sorted(counts.items())),
                   objective_names_with_setter_evidence=len(objective_setters),
                   scanner_names_with_setter_evidence=len(known & objective_setters.keys()),
                   association_scope="file-local possibilities, not path-sensitive dataflow")
    (analysis / "script_catalogue_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
