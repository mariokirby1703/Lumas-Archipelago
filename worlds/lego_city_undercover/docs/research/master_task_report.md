# Master task implementation report — 2026-11-14

## Result

A substantial implemented update, **not completion of all twelve phases**. The generated world now uses 89 source regions, known class/tool locks, progressive Astronaut delivery, independent Blackwell assignments and native story completion goals. Existing native shop/save/popup and tutorial fixes remain in place. Full traversal, native entrance gates and genuine open-world bootstrap remain outstanding.

The exact source changes are listed in changed_files.md. No commit, push, Git configuration change or live save mutation was performed.

## Concrete problems corrected

1. Default item pools could include effects with no native binding and duplicate class-character aliases. The pool now filters supported plans, excludes those aliases and makes unbound research effects explicit opt-in.
2. Astronaut and Jetpack were independent full-stage grants. Two progressive receipts now resolve deterministically by receipt index and prior legacy entitlements; reconnect never derives a stage from current RAM. Duplicate complete stages are no-ops.
3. Cosmetic class skins could bypass the randomized main class. The optional class-separation policy withholds those model grants and their entitlement masks until their class arrives. Civilian special categories remain exempt. Unsafe unmanaged-character combinations are rejected.
4. Almost every post-opening check used one Police gate. Regions now use actual district/resource sections, assignment sequence and source-declared class/tool requirements. This fixes that coarse model, but does not fill missing traversal facts by pretending they are known.
5. Early scan placement relied on an early-fill hint. With more reachable city regions, that could place the scan outside the observed opening. Requested scans are now locked onto eligible opening checks explicitly.
6. Both Blackwell assignments shared a resource name, merging completions and preventing independent persistent shield/hero detection. Native descriptor names now disambiguate them. New locations have stable distinct IDs; old aggregate IDs remain readable for old seeds.
7. The goal was an artificial token count. New seeds can goal on the final native assignment or all 15 assignments. Token mode is explicit debug/legacy behavior.
8. Cross-seed native binding was checked during delivery after checks had already been reconciled. It is now read consistently with snapshots and checked before new check/goal reporting too.
9. Each native RPC rehashed the full executable. A bounded file-identity cache avoids repeated hashing while preserving process/module and native signature checks.
10. A pinned detective hook from an older DLL produced an opaque signature error. The host now identifies the jump's owning module and refuses commands with a specific game-restart message.
11. Rebuilding an unchanged bridge could target an existing DLL filename. Rebuilds now reuse a verified artifact or choose a fresh filename; existing binaries are never overwritten.
12. An APWorld archive's filename must match its importable package root. Both build filenames now have matching roots and manifests and have been loaded and filled from their ZIPs.

## Tests and evidence

- Baseline: 273 tests, 265 passed, eight environment skips.
- Final suite: **285 tests passed, zero failures, zero skips**, including real Tk construction and synthetic native fixtures. The previously skipped C++ snippet now compiles through the installed Zig compiler (object compilation avoids Zig 0.17's broken syntax-only temporary-object rename). Exact log: build/lego_city_undercover/master_task/tests_full.txt.
- 120/120 restrictive-fill simulations passed. Twelve profiles, ten seeds each: chronological early scans, whole shields, no shields, all assignments, legacy token goal, unordered assignment access, starting Police, starting Astronaut, legacy non-progressive Astronaut, no cosmetic pool, no vehicle pool, two-player multiworld. Every run checks logical beatability and full-location reachability and records sphere sizes/progression counts. See generation_simulations.json in the same build directory.
- Both APWorlds: real ZIP import, manifest parsing, 89 regions and a successful restrictive fill. These smoke tests do not import the source world in place of the archive.
- Read-only live diagnosis: COP, Default/context 46; reviewed executable; original detective setter prologue. Native save marker read consistently. Sixteen standalone descriptors were read, including both distinct Blackwell assignment names and the police station. No native completion bit was changed to simulate success.
- Added tests cover progressive order, duplicate receipts, legacy start inventory, cosmetic withholding, policy masks, native goal predicates, split Blackwell flags, source requirements, file cache expiration/change, hook ownership and mismatched save markers.
- Existing GUI/Tk, native memory fixtures, purchase guards, serialized save flags and popup tests were retained. Test timeout/error messages from deliberate failure fixtures are expected; the final unittest result is authoritative.

## Artifacts

- build/lego_city_undercover/lego_city_undercover.apworld — recommended install.
- build/lego_city_undercover/lego_city_undercover_experimental.apworld — equivalent legacy filename with a matching alternate package root; install only one.
- build/lego_city_undercover/LCUItemBridgeTests_202b56eb5b691415.dll — current source-verified native bridge. Native C++ behavior was preserved, so the verified existing DLL is reused. It is selected by native_items_build.json.
- build/lego_city_undercover/StartLCUNativeClient.cmd — existing GUI starter, using the updated source client.
- build/lego_city_undercover/LCU_Chronological_Test.yaml — updated new-seed configuration.
- docs/research: implementation_audit.md, feature_matrix.csv, location_coverage.csv, item_effect_coverage.csv, cheat_matrix.csv, duplicate_bindings.json, coverage_summary.json, story_graph.json.
- build/lego_city_undercover/master_task: baseline patch/status/test logs, environment inventory, generation sphere report, final tests, live read-only diagnostic and snapshot. These contain local research/runtime evidence and are not uploaded or packaged as game assets.

Packaging includes only integration code and derived metadata/docs, with hashes in the build manifest. It contains no game binaries, original scripts, raw assets or save files.

## Not live validated in this pass

Progressive Astronaut grant sequence and reload, new class-skin holding behavior, detector lock denial in a real aura, both Blackwell collectible completions, real final/all-assignment goal reporting, every cheat's gameplay effect, old pinned-DLL restart handling and live cross-seed slot switching. The live work here was read-only; synthetic results are not substituted for these tests.

## Outstanding implementation

Native mission tickets require safe hotspot/invite binding before StartLevel consumption, re-arming and replay/teleport coverage. Blocking the final Door::Trigger alone risks hanging the script. Native area rollback also needs a validated transform mutation and vehicle policy. Genuine open-world setup needs a proven coherent story/objective transaction; debug presets cannot safely be applied as a partial flag list.

City traversal, building-brick economics and numerous individual pickup-bit/source mappings are incomplete. Raw clue records remain off by default. Carry Objects/Climbing/Crowbar/Fishing/Stethoscope do not have independently bound native gates; they are excluded by default. Forty cheat ownership bindings do not prove forty runtime effects. Doctor-safe and alternate Rex costume behavior need further validation. There is no release-ready or guaranteed softlock-free full playthrough claim.

## Next ingame test and save/seed policy

Use a **new AP seed** for the changed pool, regions and native goal. Preserve the existing save; an unused game slot is recommended for a clean test, but the old slot is not deleted or forcibly migrated. Old AP seeds keep their old slot data and IDs. Restart the client to load the updated Python code. Restart the game once if a different pinned native DLL was previously loaded.

Follow ../Windows_Playtest.md. Start with opening check/Police/both scans, then the two Astronaut stages, then cosmetic-before-class receipt, then one mission's token/shield/hero/red/completion. Only after those pass, test disconnect/reconnect and goals. Native pass/ticket/open-world features are not available to test as completed functionality yet.
