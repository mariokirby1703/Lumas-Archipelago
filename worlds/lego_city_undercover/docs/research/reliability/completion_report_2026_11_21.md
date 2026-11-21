# Native completion and reliability pass ? 21 November 2026

## Baseline and scope

Branch `Lego-City-Undercover-AP`, clean starting HEAD `13d2bed57`. Changes since `3e3c826` and the six requested research reports were reviewed. Baseline: 393 test executions, 386 passed and 7 skipped. Existing source work, saves, numerical AP IDs and the deliberately selected world version **0.0.1** / compatibility version 7 are preserved. No commit or push was made.

## Implemented

- Reviewed all 174 v2 pickup proofs in the bound journal: **134 newly promoted, 40 previously packaged, 0 rejected**. Shared city coverage is now **174/471**, leaving **297 unbound**. Known ambiguous bits **5848?5850** remain quarantined. Evidence identifies the original writer guard, instance registration, source/native types, native grid width and bit calculation across two observations. Structural registration is not a successful operator-controlled gameplay test for every brick.
- Added a reproducible native script extractor and persistent completion bindings for **all 65 city Superbuilts**. Each pairs the original `nState=2` save job with its objective and original AP ID. The reader works without a currently loaded build gizmo. Original per-build state overrides stale/copy-pasted scanner flags when typed job identity is available. Existing exact loaded-gizmo checks remain available for immediate early construction.
- Found the copied `SF_RD_0922_VehDrop` target in the Fort Meadows gas-station tile script. The dedicated tutorial explicitly completes `WI_FL_0708_VehDrop`; the reviewed exception uses that authoritative pairing instead of inventing an ID or rewriting the game's story.
- Extracted **42 literal automatic model rewards** from original Superbuild completion scripts. The Earwig global-found detector overlaps the Downtown call-in reward; it is excluded from **new** pools, while its old ID/source remains readable. Independent physical pickups are not globally deleted. Other uncertain sources retain explicit uncertainty; three overlapping global-found/story detectors are now excluded in total.
- Native AP model, ability, cheat, currency-batch and autosave commands now carry the expected full profile address. The game thread revalidates profile, character-bank relationship and nonempty AP marker before mutation. Profile/seed changes between the host observation and command are rejected. Existing local test RPCs retain their legacy API. Currency watermark recovery remains unchanged.
- Missing city scene/grid/cell pointers during streaming now return unresolved area information while retaining readable player XYZ, rather than dereferencing near-null addresses. Unknown districts never become guessed permissions.
- Revoking the pass for a recorded return district now prevents that checkpoint from being used. A newly received pass is distinguished from an observed physical return in the evidence.
- Diagnostics retain the last successfully read section through temporary loading/read failures. They add actor context, assignment changes, native pickup collection and player coordinates; unchanged snapshots do not manufacture repeated collections. Diagnostics do not queue AP checks.
- Read-only Google Sheets synchronization: **1,421 current rows**, **1,068 exact catalogue keys**. The importer resolves English/German headers, including the moved AP-key column, validates row numbers and preserves zero-valued costs. Design tools/classes/requirements remain explicitly unverified and are not promoted into gameplay logic.
- Added a bounded controlled native boundary-trial CLI. It requires the authorized slot3, a matching live/disk AP identity, a backup and operator-confirmed safe Auburn ground. It changes neither AP receipts nor inventory, refuses uncertain results and never self-certifies controls/collision/physics.

## Actual live observations and limits

The pinned retail process was available. All 65 typed Superbuild jobs were read; seven were complete. The previously problematic Auburn call-in has native `nState=2`, and the original job system is active. This is native state observation, not retrospective proof of its reward animation or gold-brick autosave.

The authorized slot3 was backed up under `build/lego_city_undercover/reliability_20261121/native_backup/slot3`. A native autosave request using the new expected-profile/seed guard was accepted. The file had not been rewritten at the verification deadline, and the controller still reported requested/state 2. **No new disk save was claimed; no uncertain save request was repeated.** The unchanged disk file still has the correct AP identity.

The game was in Cherry Tree Hills during the final probe. The operator has been asked to move to safe Auburn ground for the walking boundary test. Walking/running/jumping, car/bike/bus, water/air/hover, rail/passenger, pig and Behemoth physics/control trials remain pending. Synthetic success is not upgraded to live gameplay verification.

## Remaining native blockers

- Destination-selective Fast Travel gating and reload recovery without an in-memory checkpoint remain unavailable. The **90 metre** guard is retained. The client reports missing/unsupported recovery rather than issuing a distant teleport.
- Native story-entry gates before invite/StartLevel consumption and coherent Open World initialization remain unsupported in normal seeds. Existing experimental/research restrictions are preserved. There is no verified reversible whole-campaign transaction.
- The other 297 city bindings, ambiguous source aliases, some mission transient pickups and uncertain independent/automatic token relationships still need native registration/event evidence. No guessed bits, template/test checks or synthetic token completion were added.
- All four progressive families, legacy tools and out-of-order receipts have regression coverage; complete operator-controlled class/tool/save/replay playtests for every family/vehicle/creature remain necessary.
- Official localized names are used where supported; the remaining unproven names are not presented as official translations. Full reachability/cost logic remains the explicitly separate task.

## Validation

- `.venv/Scripts/python.exe -m unittest discover -s worlds/lego_city_undercover/tests`: **405 executions, 398 passed, 7 skipped**. Native synthetic fixtures include the new profile/seed rejection guard. Log: `build/lego_city_undercover/reliability_20261121/regression_tests.txt`.
- `.venv/Scripts/python.exe worlds/lego_city_undercover/tools/simulate_generation.py --count 180 --output build/lego_city_undercover/reliability_20261121/generation_simulations.json`: **180/180**, including restrictive fills, family/legacy toggles, area mode and multiworld. This proves the current AP model only, not retail beatability.
- Both packaged archive names must pass `tools/smoke_apworld.py`; their package roots, world version and restrictive fill are checked from the ZIP itself.
- Current native bridge: `LCUItemBridgeTests_f3d3621613347d12.dll`, pinned by SHA256/source digest in `build/lego_city_undercover/native_items_build.json`. Native C++ was rebuilt; older builds are retained.

## Artifacts and reproduction

- `build/lego_city_undercover/lego_city_undercover.apworld`
- `build/lego_city_undercover/StartLCUNativeClient.cmd` ? starts the repository GUI with the manifest-selected native bridge.
- `docs/LCU_Chronological_Reliability_Test.yaml` ? ordinary chronological profile, no area gate/story tickets.
- `docs/LCU_Area_Rollback_Test.yaml` ? separate opt-in near-boundary trial profile.
- `superbrick_sources_512.csv`, `template_test_sources_38.csv`, `newly_verified_pickups.csv`, `unresolved_pickup_sources.csv`, `conflicting_pickup_bits.csv`, `superbuild_job_coverage.csv`, `sheet_superbrick_merge_review.csv` in this directory.
- `../token_reward_review.csv`, `../item_effect_coverage.csv`, `../location_coverage.csv` and `coverage.json` report current source/effect coverage.
- `tools/research_superbuild_jobs.py` reproduces the 65 job bindings and automatic reward witnesses from supplied local resources. No raw game assets are packaged.
- `tools/import_location_design.py --snapshot build/lego_city_undercover/reliability_20261121/sheet_locations.json --imported 2026-11-21` reproduces the current metadata and reward review. The Google Sheet itself was not edited.

## Next actual gameplay sequence

1. Close the ordinary AP client; stand unmounted on safe Auburn ground in backed-up slot3. Use `tools/live_area_trial.py --seconds 60` for the controlled Auburn/Cherry walking trial, then explicitly report controls/collision and whether Chase returned.
2. Repeat running/jumping and car entry/exit with a native foot anchor. Do not start with cross-map Fast Travel.
3. Test the remaining vehicle/rail/creature rows independently using `native_playtest_matrix.md`; retain every unknown verdict.
4. Receive progressive stages separately, change costume, save/reload and reconnect. Collect one small/large brick, leave/re-enter and replay both mansion assignments separately.

This pass implements the reliable mechanisms described above; it does not claim every requested native feature is finished or that the game is release-ready.
