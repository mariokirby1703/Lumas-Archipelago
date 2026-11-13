# LEGO City Undercover experimental APWorld

Native research update: the collector's city bit formula is identified, 20 loaded
pickup identities have been matched to source objects, and those bindings are
enabled in the experimental client's pickup-bit detector. Monitor v13 merges
these with prior isolated observations into 25 labels and records native pickup
observations where the active scene supports them. Static mappings for all 471
city Super Brick rows remain candidates, with three colliding IDs isolated.
79 tests pass; the updated seed generates and the v13 window smoke test passes.
See docs/research/native_pickup_and_grant_paths.md for code evidence and limits.

The native navigation index now covers 57,043 unwind function ranges, 2,771,524
decoded instructions and 143,419 direct call edges. This is not a complete semantic
analysis; unresolved indirect calls and compiler fragments remain explicit.

This is an incomplete integration under development for Archipelago 0.6.8.
There is now an experimental generation APWorld, example YAML and source AP
client. This is NOT a complete playable native randomizer: item grants, reward
suppression, story/area/tool gates and open-world initialization are unavailable.
The client journals received items without applying them. No native client EXE
is shipped; the existing monitor EXE remains read-only.

Current builds:
- `build/lego_city_undercover/lego_city_undercover_experimental.apworld`
- `build/lego_city_undercover/ap_test/AP_43086033641415968754.zip`
- YAML: `example.yaml` beside this file.

The default YAML generates 1,006 locations. `include_unverified: true` opts into
raw prerequisite clues and unidentified pickups, often not independent checks.
The full catalogue contains 8,235 location candidates and 509 derived items,
plus a synthetic completion token item. IDs are deterministic; full native
bit-to-source bindings do not exist for most pickup records. No item logic is
claimed: all selected checks are reachable in AP generation. The experimental
goal is receipt of the configured number of City Completion Tokens, not a native
story-ending detector.

Run from repository root (the repo Python dependencies are required):

```
.venv/Scripts/python.exe worlds/lego_city_undercover/Client.py --connect localhost:38281 --name LCU_Test
```

Host the generated seed using the normal AP server. Native objective false->true
changes after the client's first stable snapshot can send source checks. The
client does not replay old progress from an existing save. Unbound checks can be
submitted explicitly with `/check LOCATION_ID`; active IDs/bindings are in slot
data and the catalogue CSV. Received character/tool/vehicle/access items remain
journal-only. These checks do not suppress their vanilla game rewards.

Optional `--enable-cutscene-skip`, together with YAML `cutscene_skip: true`, enables
only the verified N0CUT5 runtime permission. This is the sole implemented native
write path; it validates the EXE hash and setter signature, writes one byte, and
reads it back. The writer has not yet been exercised live. It is not part of the
read-only monitor and does not automatically advance story sequences.

`story_mode`, area-pass items and story-access items currently express requested
configuration/items only: native enforcement is NOT implemented. The generator
and slot data disclose this limitation. The world must not be presented as a
finished open-world or story-lock integration.

Research exports in ignored `notes/analysis/`:
- `ap_location_catalogue.csv`: all candidate checks, categories, source positions,
  districts where known, runtime status; unknown coordinates stay blank.
- `ap_item_catalogue.csv`: character, vehicle, ability and access items.
- `runtime_models.csv`: 1,002 registered model IDs and internal names.
- `runtime_contexts.csv`: 254 registered contexts.
- `city_superbricks.csv`: 471 city-source Super Bricks.

Source positions may require resource transforms; they are not all verified world
coordinates. Character names do not provide physical token spawn coordinates.
Tests: 77 unit tests passed; default restrictive fill is beatable; whole-shield
and quarter options are exclusive; genuine Generate.py output succeeded. Client
CLI startup was tested; no AP server/client roundtrip or native grant test has
been performed. The full research pipeline was rerun with full-file hashes.

The supplied files stay at `notes/gamefiles/`. Nothing modifies those files or game saves.
Research tools implement full-file SHA-256 inventory, PE inspection, CRC-verified CC4 v2 archive indexing,
ZIPX/DFLT extraction, and reproducible candidate mapping. The Windows bridge currently provides read-only diagnostics.

The offline pipeline now also parses all 662 JobDataMap jobs with a byte-exact round-trip, indexes 745 scripts,
and inspects all 957 extracted GIZ resource headers. Twenty tests pass.
It builds `build/lego_city_undercover/LegoCityUndercoverDiagnostics.pyz`, a standalone Python research diagnostic.
This is not a playable randomizer or the requested Windows AP client executable.

See [development](docs/development.md), [progress](docs/progress.md), and
[research findings](docs/research/reverse_engineering_findings.md).
