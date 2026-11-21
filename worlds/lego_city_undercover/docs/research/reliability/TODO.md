# Remaining native work

Current follow-up (21 November 2026): [story control TODO](../story_control/TODO.md), including the original pause-menu chapter selector, native Open World bootstrap, entrance gates and the individual outstanding Sheet points. Older coverage figures below are historical.

Historical TODO baseline from the previous closed pass. Follow-up work is recorded below; unverified native behavior is not implied complete.

Follow-up (15 November 2026): the proof review/import pipeline and missing native city-writer guard are now implemented. See pickup_binding_review.md. Live coverage remains 40/471; no new bindings were fabricated or promoted without evidence.

## P0: real gameplay validation

- Test the new bounded native checkpoint history on foot and after vehicle changes/disembarking. Geometry observation does not verify controls or collision.
- Confirm Chase-only train/tram/passenger exit through the original ClearVehicle call. Check forced/scripted seats and exit timeout diagnostics.
- Test boat, aircraft, helicopter, hover/UFO, pig and Behemoth separately, including subsequent movement and story interactions.
- Verify running/jumping and held-input border attempts with the shorter polling delay. This remains polling, not a native per-frame entrance barrier.
- Implement a reviewed Fast Travel destination gate before transition consumption. Distant travel remains unsupported; preserve the 90 metre guard.
- Investigate a native validated respawn or durable recovery transaction for loading inside locked districts. For now the client offers explicit manual recovery; never restore stale pointers.
- Review collision/navigation support for historical anchors. An older recorded pose is not an independent terrain validation.

## P0: Superbricks

- Observe the remaining 431 city sources during actual gameplay. Packaged coverage is still 40/471; this pass added zero globally verified source/bit pairs because the game was not running.
- Validate the new journal-backed two-observation binding pipeline in live play, including reload, streaming, collection before disappearance and conflict quarantine.
- Resolve duplicate tile/name/type sources using registration/instance evidence; do not use nearest-distance or static-rank guesses.
- Research mission-specific persistent source bits/registration. Mission Superbricks do not automatically use the city writer's bit scheme.
- Use tools/review_journal_bindings.py to review and promote the first actual recorded journal proofs; the validation/import mechanism is implemented, but live proof acquisition is still pending.

## P1: collectibles, rewards, saves

- Live-test both descriptor-named Blackwell assignments and transient shield/Hero detection, mission exit before summary and replay after restart.
- Complete uncertain automatic token reward relationships. Only Grace and the proven Smallisimo overlap are retired; do not delete independent physical tokens based on guide-name similarity.
- Live-test all four progressive families across receipt order, costume change, save/reload and reconnect; include legacy standalone IDs.
- Validate Cloud/file replacement protection and interrupted autosave/currency recovery on a disposable backed-up slot. Synthetic tests do not emulate Steam Cloud itself.
- Continue investigation of frame-sensitive collectible loss before a polling observation; do not invent completion events.

## P2

- Native Story Access gates before invite/StartLevel consumption, including replay and rearming, remain unavailable.
- A coherent native open-world initialization transaction remains unavailable. Do not bulk-write debug presets.
- Complete game-backed localized names where available; do not invent official character/vehicle names from internal tokens.
- Gameplay reachability logic and costs remain a separate task. The 1,337 imported Sheet rows are unverified design metadata.
- Completed: the APWorld was installed into ProgramData/Archipelago/custom_worlds after backing up and SHA256-verifying the previous archive under build/lego_city_undercover/installed_backups. Future builds still require refreshing the installed archive when changed.
- Keep the user-requested version 0.0.1. Existing item/location IDs and compatibility version 7 remain unchanged.

See native_playtest_matrix.md for the controlled live-test sequence and required observations.

## Early city Superbuilds (15 November 2026)

- Implemented loaded city-scene traversal in the SuperBuildGizmo reader. Completed instances can produce existing objective checks independently of scanner flags and story tutorial state.
- Live verified Auburn call-in SF_DO_0815_VehDrop: #cg_70_VEHICLE_DROP_GSB at (-183.200287, 1.056960, -19.791704), state 5 / flags 4; reconciliation produces location 1167252269. Check delivery uses the existing durable outgoing journal and server acknowledgements.
- This is an exact instance/world-position binding, not a nearest-object inference or a generic binding for all 65 builds. Extend verified city mappings from resource/instance evidence.
- Native job-tree activation implemented: opcode 24 enables only SuperBuild_Saves.SuperBuildsActive after native ability, typed registry, AP save binding and Max_Completed=65 checks. The original city tile scripts (verified SF_Docks_0815/ai/level10.sf) own CityObjective_SetComplete, nState=2, UpdatePin/autosave, Completed increment and SuperCounterUI. No story mission selector is advanced. Delivery invokes this after save binding/backup and requests native save. Native synthetic tests cover no ability, idempotence and foreign-save rejection.
- Live completion/counter/gold verification remains pending: the existing detective hook belongs to the prior DLL, so the new native command was rejected before mutation. Backup of bound slot3 exists under build/lego_city_undercover/native_backups/early_superbuild_20261115/slot3. Restart is required. Determine whether the already-built but unrecorded gizmo survives reload; if not, a separate reviewed native recovery transaction is still needed. Do not label this case recovered without readback.

## Follow-up, 21 November 2026

See completion_report_2026_11_21.md for the current evidence. Earlier counts above are historical.

- Implemented/promoted: 134 additional structural city proofs, 174/471 total; 297 remain unbound. Bits 5848?5850 remain quarantined.
- Implemented: persistent source-derived job/objective bindings for all 65 city builds; typed live reader found all 65 and seven complete. Original Auburn call-in nState=2 is observed; original reward animation/gold save is not retroactively verified.
- Implemented: game-thread expected-profile/seed guards for ordinary AP grants, currency batches and saves; loading-safe location/diagnostic handling; revoked-anchor rejection; pass receipt versus physical-return evidence.
- Implemented: English/German header-based Sheet importer, 1,421 current design rows / 1,068 exact keys; 42 original Superbuild automatic reward witnesses and one further overlapping Earwig found detector excluded from new seeds only.
- Native save request accepted in backed-up slot3; new disk rewrite still pending at readback. Do not repeat uncertain mutations or claim disk success from the RPC.
- Next live action: operator moves to safe Auburn ground, ordinary client closed, then controlled tools/live_area_trial.py. No real boundary/vehicle/creature controls/physics trial completed in this pass yet.
- Remaining native story entrances, Open World, distant travel/reload recovery, incomplete names/relationships and gameplay logic retain the unsupported/experimental status above.
