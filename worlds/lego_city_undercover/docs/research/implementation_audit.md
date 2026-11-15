# Implementation audit — 2026-11-14

The [15 November development report](next_major_pass_2026_11_15.md) supersedes the feature status below where changed, including progressive families and the experimental boundary return.

This document supersedes older completion/logic statements in chronological_test_status.md and the historical native_item_delivery_status.md. This is still an experimental integration, not a complete or proven softlock-free randomizer.

Baseline: branch Lego-City-Undercover-AP, dcd83c4531a741622e62c9273dddf6f739ca0e1d. Baseline tests: 273, 265 passed, eight environment skips. Existing station-gold research was retained. No live game/save mutation, seed rewrite, commit or push was performed for this task.

## Implemented in this pass

- Progressive Astronaut resolves AP receipt order into Astronaut and then Jetpack. Legacy class/Jetpack start inventory consumes the corresponding stage. Further copies are explicit no-ops, not invented currency. Stage resolution never depends on volatile RAM. Original item IDs remain available for old receipts.
- Default pools exclude unbound effects and primary-character aliases when their equivalent class abilities are included. Rex Fury uses its roster-backed character model rather than a nonexistent native ability name. Existing unapplied symbolic Rex receipts have one narrowly scoped migration; other recorded plans remain immutable.
- Optional class separation holds class-specific cosmetic skins until the main class is entitled; civilian special categories are unaffected. Old seeds without the new flag retain previous semantics. Class separation with managed abilities but unmanaged character rewards is rejected.
- Regions now represent the opening, police station, actual district identifiers, 15 assignment entries and native resource sections. Source lock metadata supplies class/tool requirements. Assignment order is represented separately from district exploration. Unknown requirements are not presented as verified traversal logic.
- Requested early criminal/detective scans are explicitly placed on observed opening checks, rather than relying on an early-fill request that could now select another reachable region.
- Final-assignment native completion is the default goal. All 15 native assignments is an alternative; token collection is an explicit debug goal. Old seeds missing the option keep their token semantics.
- Blackwell's two assignments have independent completion, hero and shield keys. Old aggregate IDs are retained for old seeds and excluded from new pools. Both native descriptor names are required; no guessing by current scene.
- Cross-seed native markers are checked before new checks or native goal reporting. The marker is sampled twice around snapshot collection. Existing offline achievements in the same save are still reconciled.
- Exact executable hashing has a five-second file-identity cache with expiration and replacement checks. Process/module identity and native mutation signatures are still checked. A pinned detective hook from another DLL produces an explicit game-restart error before a command is sent.
- Repeat DLL builds reuse an already verified binary or choose a new filename; an existing DLL is never overwritten.

## Coverage, not inflated completion claims

Run `tools/audit_implementation.py` to regenerate location_coverage.csv, item_effect_coverage.csv, cheat_matrix.csv, coverage_summary.json and story_graph.json. These are factual indexes; a native detector accepting a key is not a live verification of each location.

The catalogue contains thousands of raw candidates. `include_unverified` stays off. Some default Super Brick candidates still lack a validated individual bit/source mapping; full collection coverage is not established. Coordinates are retained in their original resource space and must not be treated as player/world coordinates without a proven transform. Malformed district labels are routed to unresolved sources rather than manufactured district names.

The source graph extracts 213 developer presets and 11 transition scripts, preserving variable/job names, doors, hotspots and state edges. Developer presets invoke debug unlock routines and bulk story initialization. They are evidence, **not a safe write recipe**.

## Native entrance and open-world blockers

Native story tickets and district rollback are not implemented. Normal generation rejects enabled ticket/pass pools unless `experimental_items` is explicitly selected; those symbolic research items do not acquire native effects by this opt-in.

The transition scripts wait for a generic invite, consume StartLevel, then enter a one-shot TriggerDoor state. Simply blocking Door::Trigger after that point can strand the job. A correct gate must intercept the original hotspot/invite before consumption, preserve re-arming, and cover replay/summary/teleport entries too. The source names are indexed in story_graph.json; none is claimed as a validated runtime registry binding.

`story_mode: open_world` currently changes AP assignment ordering only. No postgame bootstrap is performed. Native debug presets set story jobs, world objectives, unlocked abilities and completion-dependent scene state together; writing a convenient subset can reproduce the earlier police-station softlocks. There is no safe complete bootstrap transaction or rollback proof yet. Existing tutorial-specific fixes are preserved instead.

Carry Objects, Climbing, Crowbar, Fishing and Stethoscope remain excluded standalone items by default. Grab is a combat-related flag and is not falsely equated with carrying quest props. Class/tool interactions and Doctor exceptions need their own native call-path proof. Detective Scan has an actual setter hook with synthetic tests, but no fresh live aura revoke/grant test was performed in this task.

All 40 cheat ownership effects are indexed separately from discovery and runtime activation. A grant allows ownership; it does not force the Extras toggle or prove the visual gameplay behavior of all 40 effects. See cheat_matrix.csv.

## Validation and artifacts

`tools/simulate_generation.py --count 120` performs real restrictive fills, full-location reachability and goal checks across 12 profiles, including two-player seeds, shield options, starting classes, disabled cosmetic/vehicle pools and both Astronaut modes. Sphere sizes/progression counts are stored in build/lego_city_undercover/master_task/generation_simulations.json. Passing this model is not an in-game completion proof because city traversal remains partial.

`tools/package_apworld.py` produces both lego_city_undercover.apworld and the compatibility experimental filename, with matching package roots, deterministic archive contents, AP manifests and hash metadata. It packages integration code, derived metadata and documentation only. The native DLL remains the separately verified version in native_items_build.json. Do not install both APWorld filenames simultaneously.

Remaining work: complete city traversal requirements and economics; validated pickup-bit/source mappings; native ticket gates; actual open-world initialization; full chronological ingame playthrough; per-cheat effect validation; richer chapter/replay transitions. These are outstanding implementation work, not completed features hidden behind a disclaimer.
