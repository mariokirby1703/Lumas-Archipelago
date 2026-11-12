# Development

Run from the repository root with 64-bit Python 3.11 or newer. Research tools use the standard library.

The complete offline pipeline can be reproduced with:

```powershell
.venv/Scripts/python.exe worlds/lego_city_undercover/tools/research_pipeline.py --with-disassembly
```

This rehashes the original files, extracts and validates selected resources, parses job defaults, indexes script
and GIZ evidence, runs the automated tests and builds an asset-free standalone diagnostic archive. Capstone is needed only
for --with-disassembly and is present in this repository virtual environment.
The pipeline writes notes/analysis/pipeline_validation.json with report hashes and explicitly unverified gameplay status.
It never starts the game or writes to it. --skip-inventory reuses old hashes and records that limitation.

```powershell
python worlds/lego_city_undercover/tools/inspect_game.py
python worlds/lego_city_undercover/tools/archive_index.py
python worlds/lego_city_undercover/tools/harvest_research.py
python worlds/lego_city_undercover/tools/map_candidates.py
python worlds/lego_city_undercover/tools/job_data.py
python worlds/lego_city_undercover/tools/script_catalogue.py
python worlds/lego_city_undercover/tools/resource_catalogue.py
python -m unittest discover -s worlds/lego_city_undercover/tests -v
python worlds/lego_city_undercover/bridge/diagnose.py
```

The first command reads about 20.2 GB to hash the complete supplied installation.
All proprietary data, raw indices, extracted scripts and full mapping dumps stay under ignored `notes/`.
Extraction validates index bounds, CRC name association, output paths and declared sizes.
An existing extraction must match its source byte-for-byte; it is never overwritten.

The repository uses World/Region/Location/Item APIs, CommonClient and LauncherComponents.Component.
ChecksFinder was inspected for basic region/item lifecycle conventions. Local docs/world api.md,
docs/style.md and docs/apworld specification.md were reviewed. Existing sonic_colours files mentioned
in the IDE context were not present on disk when inspected.

Do not register an empty world as playable. Next establish a callable engine action or a verified state structure,
then implement checks and item grants together. Symbols are not function signatures or addresses.
The eventual bridge should use local authenticated IPC and execute engine actions on the game thread.
External diagnostics intentionally never request write privileges.
Use --research-state for named experimental ability arrays; --objectives for the statically derived objective reader.
Neither option enables AP checks or grants. The objective reader has no live completion validation yet.
Action cross-references can be reproduced with .venv/Scripts/python.exe tools/action_xrefs.py
(using the full world-relative tools path from the repository root).
The optional Capstone dependency is already available in this checkout virtual environment.

Packaging must use the repository's Build APWorlds component once a genuine world exists.
The local .apignore was checked using Utils.read_apignore and match_tree_files.
No APWorld/client release has been built.

A separate research diagnostic is built at build/lego_city_undercover/LegoCityUndercoverDiagnostics.pyz.
It contains only an explicit allowlist of bridge Python files, an entry point and file hashes.
It requires installed 64-bit Python 3.11+ and has no third-party runtime dependencies.
It is not the requested AP client EXE and does not implement networking, checks or received items.

The inventory reader uses generated factual roster metadata from tools/collection_data.py. Rebuild this manifest
after extracting chars/collection.txt; the full research pipeline includes the generator.
No game resource is loaded for APWorld registration; no World class is currently registered.
