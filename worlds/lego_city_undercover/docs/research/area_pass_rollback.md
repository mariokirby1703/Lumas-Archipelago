# Native area rollback prototype — 2026-11-15

This supersedes the earlier statement that no position mutation path exists. It is an explicit experimental test mode, not complete native district enforcement. No movement RPC was executed in the user's game during development.

## Policy

Auburn (`SF_Docks`) is always allowed, without a randomized pass. Canonical passes for the other 21 districts are client-policy entitlements, not writes into the game's ability array. Legacy capitalization/alias IDs are preserved, but only canonical names enter the experimental pool.

The first Cherry Tree Hills pass (`SF_Residential`) is placed locally on one of three checks the user actually reached in a fresh Auburn save before Police: the Auburn booth or the two originally observed small Super Bricks. Generation rejects an unavailable/excluded opening instead of placing this pass behind itself. Requested Police/scans are still placed separately. The independent sheet requirements remain unverified and are not compiled into access rules.

Native movement is enabled only by both `area_pass_items` and `experimental_area_restrictions`, with native client operations enabled. Normal YAML keeps both off. All other unsupported symbolic progression stays off. Read the limitations before treating this as a playable Area-Pass mode.

## Native paths

Supported EXE SHA256 remains `624fed07274bbd105d1d571ecb97a290df6f6f0aff76898c516890da6d136f76`.

- The name getter `0x17610` is **not** the teleport implementation. Its vtable identifies script handler `0x114dd0`, which calls `0x6709f0(actor, vec4*)`. That routine enters `0x670c00`, checks the native pending teleport addon and updates the character through the original transform/collision path. The complete eight-byte wrapper prefix is checked.
- Vehicle script handler `0x11b860` reads/preserves a 4x4 transform and calls `0x4abe70(vehicle_interface, matrix*)`. That original routine handles native transform/physics synchronization. Its fifteen-byte prefix is checked. Momentum, aircraft, boats and attached vehicle combinations still need live tests; no unverified velocity fields are cleared.
- `Character_GetVehicle` handler `0x112c80` uses the weak pair from actor `+0x428/+0x430` via `0x6d00`. The reader checks the same liveness field and dereferences the vehicle only while live. Only the reviewed `0x506fe0` base-vehicle transform getter is accepted for movement. Unknown layouts are rejected.
- On foot, only `Default` context 46 is accepted. Mounted movement requires `RideObject` 157. `RideAlong` 11, `DropPoint` 27, jumps, scans and scripted contexts defer. The original alive/context checks remain in the command dispatcher.

Opcode 21 records an allowed current pose, opcode 22 returns to that captured pose. The caller cannot supply arbitrary coordinates or actor addresses. The native checkpoint lives in the pinned DLL, with AP binding, profile, world, actor, current vehicle/control reference and native district hash. It is replaced only after a successful allowed-area capture. Capture/restore does not manufacture an AP receipt, pickup flag, story stage or save marker.

An already backed-up, uniquely bound fresh save may have an empty currency watermark before its first filler receipt. This is allowed without writing a fake watermark. A nonempty mismatched marker always rejects the command. Return additionally requires the same captured native identities and a current target tile still resolving to the captured district.

The native district comes from the current world grid and exact tile prefix, with numeric suffix validation. It never comes from nearest collectibles. Standalone interiors are independently excluded using the actor's registered scene, even if a background city grid remains resident. `NY_Downtown_East` is not confused with `NY_Downtown`.

## Limits

- Returns are limited to **90 metres** from the most recent native checkpoint. There is no guessed global Auburn spawn and no distant Fast Travel rollback.
- The checkpoint is process/actor/vehicle specific. Restarting the game, loading inside a locked area, changing vehicles while locked, or an unsupported vehicle getter may leave no usable anchor. The client reports this and does not teleport blindly.
- Enforcement is a host polling loop, not a transition interception or native per-frame barrier. Boundary overshoot, pickups before the next poll, trains, cutscenes, respawns and long-distance transitions are not fully covered. This must remain experimental.
- A timeout or uncertain command is not automatically replayed. Explicit pre-mutation busy rejections may defer/retry. Returning to an allowed area is observed separately; an accepted RPC or allowed-area observation is not claimed as proof of exact restored coordinates.
- There is no persisted cross-restart rollback anchor. Story entrance tickets and genuine open-world bootstrap are still unfinished.

## Evidence and testing

Native fixtures execute the same guard code against synthetic city grids, actor/vehicle transforms and stand-ins for the reviewed teleport bodies. They test both movement paths, no-anchor/area/seed/vehicle mismatch, interiors with resident grids, nonfinite matrices, unknown signatures, range limits and fresh-slot watermark preservation. These are not live game movement tests.

The GUI shows translated area status and offers **Gebiet-Diagnose kopieren**. Its bounded event report contains timestamp, scene, native tile/district, sampled player and ride positions, checkpoint and AP binding. Read-only capture, requested position mutation and native save writes are explicitly distinguished. Unchanged snapshots are not appended each poll.

For the first live test, use `LCU_Area_Rollback_Test.yaml`, a new seed and a free save slot. Restart game/client for the new DLL. Stay in Auburn long enough to see a confirmed checkpoint, then walk over the Cherry Tree Hills boundary before collecting its pass. Test walking first, then the same car after waiting in Auburn for a vehicle checkpoint. Only after this succeeds collect the pass and verify the boundary permits entry. Do not use Fast Travel as the initial test. Export the area report if any guard rejects the action.
