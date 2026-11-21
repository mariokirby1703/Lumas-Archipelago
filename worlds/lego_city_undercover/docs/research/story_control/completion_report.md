# Story control implementation pass — 21 November 2026

Version remains **0.0.1**. This pass implements additional read-only native check detection and documents the remaining native control work. It does not complete the requested Open World or chapter-selection system.

## Implemented

- Reviewed all 150 populated points in the complete Story Progression Sheet tab. [Full review](story_point_review.csv), [individual outstanding points](story_point_todo.csv).
- Added 14 source-bound story milestone locations. Their detector requires the original typed Bool completion field, not AP ownership, current story stage or an achievement. The `story_milestones` YAML option can disable them. Existing 35 location mappings are reused without duplicate IDs.
- Unverified traversal logic for these new milestones cannot host progression items. The remaining 55 unresolved milestones and 46 internal/entry control events are not manufactured into checks.
- Bound the seven existing mission constructions to original script/template identities: Mine Cable Car, Temple Dragon, Bank Truck, Construction Crane, Museum Plane, Museum Dinosaur and Scrapyard Crusher. Six receive new scene/name/cost-specific detection; the previous Mine binding is retained. Final native state and completion flags are required. Duplicate loaded instances are quarantined. No duplicate construction locations were added.
- Added a typed read-only chapter event reader. It explicitly reports no active chapter, no activation support and no AP-check eligibility: the achievements bank is not proven isolated per save.
- Added a final snapshot identity check after late actor/story reads. A profile, actor, world or AP binding change aborts the snapshot rather than mixing two saves/scenes.
- Ordinary new Open World seeds now fail clearly because the native bootstrap and original pause menu are absent. Explicit experimental AP-graph research compatibility remains available; it does not implement native Open World.
- Exported 21 offline Locations Sheet patches: 14 new milestone rows and seven existing mission construction updates. The online Sheet was not modified.

## Evidence and validation

The original chapter-start action at RVA `0x84f0` changes achievement event flags; it does not start/select a chapter. Completion uses `0x84b0 -> 0x7cf0`, with masks at manager `+0x110/+0x188`. Original pause assets and drawer lookup were located, but allocation, callbacks, focus and teardown are not established. No speculative pause-menu or chapter writes were made.

Analyzed original resources include `GAME7/gui/blend/frontend/frontendmain.baml`, `fe_button_04.baml`, `gui/blend/e3_drcpause/mainwindow.baml`, city Flow_Setup/Flow_Completed scripts and 696 extracted mission script/list resources. The seven construction entries in [mission_superbuild_review.csv](mission_superbuild_review.csv) identify their individual completion scripts and GAME4 builder templates. Only derived metadata is distributed; original extracted assets remain ignored.

All existing item/location IDs are retained. Regression suite: **419 test executions, 412 passed and seven skipped**. Restrictive fill simulation: **180/180**, including one/two-player, optional milestones, class families and experimental area/story profiles. These are AP logical checks, not proof of native playability.

Read-only live probes recorded the chapter bank and typed story flags in the running game. No save was reset, no chapter was activated, and no game writes or AP messages were issued by those probes. The six non-mine build bindings still require live collection/reload tests. The native DLL source is unchanged in this pass; the build verifier checks the existing versioned DLL rather than claiming a new native implementation.

## Delivery and remaining work

Build: `python worlds/lego_city_undercover/tools/package_apworld.py`. Both archive filenames must pass `tools/smoke_apworld.py`; install only one. Restart the source client for the reader changes. A new seed is required to include the 14 added milestone locations; existing seeds retain their original slot-data catalogue.

The [prioritized TODO](TODO.md) records the unimplemented original pause-menu chapter selector, all 15 independent chapter transactions, native Open World initialization, pre-consumption mission gates, destination travel gates, save isolation and live movement/construction validation. No external chapter GUI was added as a substitute.

## Launch and test

1. Restart the AP generator after installing the new archive. Use the existing chronological YAML with `story_milestones: true`; generate and host a new seed to test the additional locations. Do not select ordinary Open World yet.
2. Start the game, then `build/lego_city_undercover/StartLCUNativeClient.cmd`. Enter the new server address/port, slot name and optional password in the existing GUI. The launcher uses the repository client and manifest-selected versioned DLL.
3. Use a backed-up test save bound to that seed. Never attach a different seed to an already-bound production save. No reset is required for an existing seed when testing only compatible reader improvements.
4. Observe a listed original story action or mission construction and copy the client/monitor log. Report mission, scene, event and whether the check survives reconnect/reload. Mission constructions require the final build event, not merely approaching the platform.
5. Native chapter selection/Open World and pre-consumption access gates cannot be tested as working features in this build; they remain in TODO.
