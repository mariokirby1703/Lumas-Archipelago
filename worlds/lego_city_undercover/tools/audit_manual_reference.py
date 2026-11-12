"""Inspect a supplied Manual APWorld as data, without importing or extracting code."""
import argparse
import ast
import collections
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile


def audit(path: Path) -> dict:
    with ZipFile(path) as archive:
        roots = [n[:-len("data/game.json")] for n in archive.namelist() if n.endswith("/data/game.json")]
        if len(roots) != 1:
            raise ValueError("Expected one Manual world root")
        root = roots[0]
        def read(name):
            info = archive.getinfo(root + name)
            if info.file_size > 4_000_000:
                raise ValueError("Reference member exceeds audit limit")
            return archive.read(info).decode("utf-8-sig")
        def data(name):
            value = json.loads(read("data/" + name + ".json"))
            return value.get("data", value)
        items, locations, regions = data("items"), data("locations"), data("regions")
        names = {i["name"] for i in items}
        syntax_errors, functions, function_refs = [], {}, set()
        for member in archive.namelist():
            if member.startswith(root) and member.endswith(".py"):
                source = read(member[len(root):])
                try:
                    tree = ast.parse(source, filename=member)
                except SyntaxError as error:
                    syntax_errors.append(dict(member=member, line=error.lineno, message=error.msg))
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith("Can"):
                        returns = [ast.unparse(n.value) for n in ast.walk(node) if isinstance(n, ast.Return) and n.value]
                        functions[node.name] = dict(member=member, line=node.lineno, returns=returns)
                        for call in ast.walk(node):
                            if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                                and call.func.attr == "has" and call.args
                                and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str)):
                                function_refs.add(call.args[0].value)
        counts = collections.Counter(r["name"] for r in locations)
        rule_refs = set()
        for r in [*locations, *(v for v in regions.values() if isinstance(v, dict))]:
            for token in re.findall(r"\|([^|]+)\|", r.get("requires", "")):
                rule_refs.add(re.sub(r":\d+$", "", token))
        return dict(source=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    creator=data("game").get("creator"), location_count=len(locations), item_count=len(items),
                    categories=dict(collections.Counter(c for r in locations for c in r.get("category", []))),
                    duplicate_location_names={k:v for k,v in counts.items() if v>1},
                    unknown_location_regions=sorted({r.get("region") for r in locations if r.get("region") not in regions}),
                    undefined_item_references=sorted((function_refs | rule_refs)-names),
                    python_syntax_errors=syntax_errors, helper_rules=functions,
                    source_locations=locations, source_regions=regions,
                    instructions_executed=False, native_game_logic_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    report = audit(args.archive)
    output = Path(__file__).resolve().parents[1] / "notes/analysis/manual_reference_audit.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("source_locations", "source_regions", "helper_rules")}, indent=2))


if __name__ == "__main__":
    main()
