# Area-pass / opening-region hardening (2026-11-15)

Base branch: `Lego-City-Undercover-AP` at `3e3c826cec65be673ec141a1b7694988466db696`.

This is a **source patch containing complete replacement files**, not a new APWorld or a completed native game verification. Use only with this branch/compatible descendant. Previous save, DLL and AP IDs are preserved.

## Important correction: Auburn starts free, HQ is NOT Auburn

- The player starts in **Auburn (`SF_Docks`)** and never needs an Auburn Area Pass.
- **Cherry Tree Hills (`SF_Residential`)** requires its own pass when `area_pass_items: true`.
- The Police Station is geographically accessible through Cherry Tree Hills; its standalone resource path is not a reason to classify it as an Auburn check.
- Older `opening_no_police.json` describes checks available without the **Police ability**, not checks geographically located in Auburn. Mixing the two was a real softlock risk with area passes on.
- `regions.py` now puts the Police Station behind the Cherry Pass and prevents station rewards / the COP wardrobe from being treated as Auburn opening checks in area-pass seeds. Historic no-area-pass behavior remains unchanged.
- `_opening_key` now explicitly uses only observed Auburn source keys for early local Police / Scanner / Detective Scan item placements. The Cherry Pass is still locked locally into one of the three designated Auburn starter checks.
- `area_pass_items` with `story_mode: open_world` is now rejected rather than pretending a postgame save can be bootstrapped safely. This does not affect native `story_mode: linear`.

## What the native rollback already implemented in the latest commit

The repo already contains a native DLL command for checkpoint capture (opcode 21) and close-range return (opcode 22) implemented in `bridge/native/area_return.h`. It validates the pinned executable, active actor, world grid tile, save binding and original transform routine. The return accepts no arbitrary host-supplied coordinates, and only targets a recorded pose of the same actor **and the same vehicle identity** if mounted. Its physical return limit is 90 metres. The Python controller calls that existing implementation.

A vehicle return moves the supported base-vehicle transform via the native game routine; the rider is expected to follow the vehicle. Vehicle momentum, boats, aircraft and persistent transform changes require **live testing**. Do **not** claim the driver and vehicle always recover safely without that test.

## New controller changes

- A controller is reset on PID/seed/save binding changes **before** any backup state check, so stale UI checkpoint data cannot outlive its connection.
- New context (on-foot to RideObject, or vice versa) captures an allowed-area checkpoint immediately, even within the normal 650 ms refresh interval. This helps avoid attempting to return a car to a previously captured on-foot pose.
- Native responses are classified as **accepted**, **definitively rejected before mutation**, **temporarily busy**, or **uncertain**. A native range/identity/signature rejection never causes automatic retry in the locked area.
- A timeout/fault may have moved the actor; it is not replayed. The controller waits for a fresh observation of an allowed area before recapturing.
- Explicit `NativePlayerBusy` is a rejection before mutation and can retry on the next eligible poll.
- Diagnostic reports expose return request, context, checkpoint, identity and distinguish a requested transform write from a persisted save write. No checkpoint save writes are manufactured.
- Empty, malformed and non-city tile identifiers are rejected rather than guessing a nearby area.

## Critical limitations remaining

**Do not enable this in a valued save or publish it as release-ready Area Pass enforcement.** The implementation is still polling-based, opt-in and experimental.

- Last allowed location is an in-memory checkpoint, not a persisted save-spawn. Reloading inside a locked area may have no safe checkpoint.
- The native return refuses beyond 90 m. Distant Fast Travel, teleport transitions and loading into a forbidden area are not solved.
- Some vehicle types may not share the reviewed native transform getter. The DLL rejects unknown layouts instead of writing them.
- Even a successful DLL command is not a proof that vehicle momentum, collisions and player animation leave the game in a playable state.
- The 22 district pass regions are connected abstractly from `LEGO City`; this is **not** the fully validated city-road traversal graph. A progression fill passing logical reachability is not proof of native beatability.
- Unknown source ability rules, story tickets, open-world save initialization and 471 city Superbrick bindings remain partially researched.
- The Google Sheet is a **human-facing design/research source**, not complete native truth. Do not treat its outfit/ability/auras as verified locks without game evidence.

## Tests

Additional pure/synthetic controller tests: `tests/test_area_pass_hardening.py`.
Integration regression tests (require complete Archipelago repo): `tests/test_area_region_start.py`.

They cover Auburn always open, Cherry Pass ownership, strict tile prefix parsing, policing station not an Auburn placement, capture after vehicle mode switch, busy retry, definite native rejection, timeout no-repeat, bound slot switch, and unsupported scene/context safety.

The pure tests were run in an isolated environment against stub native functions and passed (13 tests). **The full Archipelago test suite, APWorld packaging, C++ native fixture compilation, and real Steam game movement were not available here.** Run them in the checked-out repository before any real playtest.

## Recommended first playtest

1. Back up the entire Steam save directory and use an **unused game slot**.
2. Confirm game executable hash and native bridge manifest are supported; restart game and client for changed files.
3. Generate a **new** seed using `docs/LCU_Area_Rollback_Test.yaml`. Install only one APWorld package.
4. Verify the first area status says Auburn checkpoint captured while on foot. Cherry Tree Hills and the Police Station should be inaccessible by AP logic before the Cherry Pass.
5. Cross the Auburn/Cherry boundary on foot *without* Cherry Pass. Verify the native player is returned to the observed Auburn checkpoint and can still move; export the area evidence.
6. Return to Auburn; enter an ordinary supported car; stay there until a **new vehicle checkpoint** is recorded. Cross the same border. Verify that the rider and car return together, with working controls, no clipping and no crash.
7. Collect the local Cherry Pass and verify the border is now permitted. Ensure the Police Station is reachable only after this entitlement.
8. **Do not use Fast Travel, aircraft, boats, save reload in a locked area, or cross-map entry for the first test**. Those require separate native research.
9. If the gate returns `return_rejected_safe`, `return_uncertain` or `locked_area_without_checkpoint`, stop automated tests on that slot, export the report and reload a safe backup. No uncontrolled repeated teleport should be attempted.

### Developer follow-ups

- Trace a native safe respawn/return API supporting a chosen valid scene and existing world checkpoint across long-distance transitions. Do not remove the 90 m bound just to appear to support it.
- Verify vehicle type getter and velocity/physics after native return; determine a safe on-foot fallback if the vehicle has changed, without detaching the actor incorrectly.
- Add a validated adjacency graph and travel routes between districts, including bridges, trains, ferries, underground passages and menu Fast Travel.
- Add native pre-transition gating where possible, instead of relying exclusively on after-entry rollback.
- Complete automatic token/source reward reconciliation and verified per-object requirements; the updated Sheet row count is not a native completeness claim.

Validation addendum: the subsequent combined pass completed 343 unittest executions and 180 seed simulations. See next_major_pass_2026_11_15.md. Live movement remains unverified.
