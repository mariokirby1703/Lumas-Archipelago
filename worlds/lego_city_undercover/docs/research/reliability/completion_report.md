# Native reliability pass — 15 November 2026

Baseline: clean HEAD e9247703c; 359 unittest executions passed. User-requested version 0.0.1 retained. No commits, pushes, save deletions or live gameplay mutations were performed.

## Completed changes

- Native checkpoint history retains 16 observed poses. A return can prefer an older pose in the same allowed district with the same actor/ride identity. Original type/signature/binding/tile and 90 metre guards remain.
- First capture after a controller reset clears obsolete native history. Actor/profile/bank changes invalidate host identity. Creature checkpoints also compare target model/controller identity.
- Native replies expose requested pose and movement kind. Diagnostics distinguish RPC acceptance, observed allowed district and pose distance from unverified controls/physics/save behavior.
- Changed vehicles can use the separate foot checkpoint. Unconfirmed passenger exits stop repeated exit polling after five seconds while still allowing a later observed dismount to complete recovery. Unknown RPC outcomes remain latched.
- Area policy runs before inventory delivery; post-return snapshots are refreshed before further grants. Experimental area polling delay is 250 ms rather than one second. This is not native event interception.
- Native save resolution/backup precedes check reconciliation. Profile/actor changes reset cached identity even in passenger context. A stable disk file bound to another AP seed blocks native writes and reconciliation, including possible Cloud/file replacement.
- New city binding observer checks two stable typed source registrations and persists exact proofs in the seed-bound SQLite journal. It retains mappings across streamed tile unload/reconnect, quarantines conflicts and enriches detection without changing seed/journal identity. No nearest-position matching or global source-index offset is used.
- Bounded change-only diagnostics capture area/scene, pickup-bit/objective/model changes, structural bindings, grants and disk save confirmations. The GUI exposes a collectible evidence copy button, binding counts, save-slot path and seed; title shows version 0.0.1.
- Mansion shield/Hero detection can resolve the original assignment descriptor and keep the two Blackwell missions separate. Unknown descriptors remain unresolved.
- All 1,337 current Sheet rows imported; 1,068 exact existing native key matches. Requirements remain explicitly unverified. Native IDs were checked against baseline and unchanged.
- Reproducible reports split 512 gameplay Superbrick definitions from 38 templates/tests/additional sources. Coverage remains 40 packaged city bindings, 431 unresolved, zero newly verified global mappings this pass.

## Validation

- Full final suite: 374 unittest executions, OK, including Windows GUI and native synthetic fixtures.
- Restrictive-fill simulations: 180/180 passed across the existing 18 profiles. This does not establish native playability or full location logic.
- Native bridge rebuilt and source/hash verified: LCUItemBridgeTests_696cc2aa29845c3e.dll.
- Final APWorld ZIP imports and restrictive fill are smoke-tested after packaging.
- The game was not running during the read-only probe. No new live movement, collectible, creature, progressive-tool or Steam Cloud tests are claimed. Earlier user confirmations of walking and tram rollback are preserved as historical feedback, not converted into tests of this new DLL.

## Deliverables

- build/lego_city_undercover/lego_city_undercover.apworld; experimental compatibility filename is a separate package-root alias. Install only one.
- build/lego_city_undercover/StartLCUNativeClient.cmd launches the repository GUI/native client; no standalone networking EXE is claimed.
- The native_items_build.json manifest selects the verified versioned DLL. Restart game and client for this native build.
- LCU_Chronological_Reliability_Test.yaml: ordinary chronological profile with area restrictions off.
- LCU_Area_Rollback_Test.yaml: explicit experimental area profile. The user's existing LCU_Chronological_Test.yaml area-on preference is preserved.
- docs/research/reliability: source catalogues, unresolved/new-binding CSVs, coverage.json, TODO.md and controlled native playtest matrix.
- build/lego_city_undercover/next_pass/reliability_final_tests.txt and reliability_final_simulations.json contain the final validation logs.

The prior installed archive under ProgramData was inspected and is older; it is not silently replaced. Native Fast Travel destination gates, locked-area reload recovery, native Story Access and open-world initialization remain unfinished. See TODO.md for the exact follow-ups and live-test order.
