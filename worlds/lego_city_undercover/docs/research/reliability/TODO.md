# Remaining native work

The user ended this pass to conserve usage. No additional features should be inferred as complete from the packaged build.

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
- Review and promote recorded journal proofs into a shared binding release only after source/type/identity and collision checks.

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
- Install the new APWorld in the user's Archipelago installation when ready. This pass builds the deliverable; the previously installed archive was older and has not been overwritten.
- Keep the user-requested version 0.0.1. Existing item/location IDs and compatibility version 7 remain unchanged.

See native_playtest_matrix.md for the controlled live-test sequence and required observations.
