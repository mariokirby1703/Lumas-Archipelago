# Sonic Colours PAL SNCP8P Rev0: V7 strict per-stage Movement Request Gate

**Status: experimental, offline simulated; not verified in live Dolphin.**

## V6 user evidence (2026-10-12)

| Stage | Hook entries | Sonic matched entries | Denied | Host controller | Last hook controller | Native state fields |
|---|---:|---:|---:|---|---|---|
| New Game stg110 | 153 | 150 | 43 | 0x80B58A40 | 0x80B58A40 | current=2 request=2 |
| stg130 | 256 | 192 | 50 | 0x80B5BA80 | 0x80B4C000 | current=0x92EAA964, request=0x92EAC334 |
| Return stg110 | 388 | 192 | 50 | 0x80B473C0 | 0x80B57A40 | current=0x36C9539C, request=2 |

Counters are cumulative. The 103 new handler entries between the first two reads included only 42 matched owner requests and 7 denials; the next 132 handler entries produced **zero** new owner matches. These observations do not prove the exact cause of controller state corruption or that every movement was accessible. They show the old actor matching/arming scheme did not remain reliable across scene transitions.

## Changes in V7

- Native PPC hook is still at `0x8003388C`, before original `cmpw r4,r0` and state request processing.
- **Exact per-stage controller identity**: the handler will only inspect a request whose native object pointer `r31-0x40` equals the precise controller address explicitly authorized by the host for the current observed stage. The host mailbox is *not* a general boolean arm flag as in V6. This prevents a controller created before client attribution from being restricted simply because V6 remained armed after a stage transition.
- Host only arms on `gameplay`, `alive`, scene verified, stable_polls >=3, non-null `stage_epoch`, verified player/controller vtables and owner backreference, and `current_id/requested_id` in nonnegative 0..127. Otherwise it disarms.
- PPC also fails open when `current_id` or `requested_id` exceeds 127 (including 0xffffffff), so a recycled/uninitialized controller does not receive movement denials. This matches the invalid values from V5/V6.
- In the host poll, the control word is also set to zero for non-gameplay snapshots, allowing stage-transition disarm as soon as the host observes a menu/results/transition frame.
- Existing permission map unchanged: Double Jump (8), Mid-Air Boost (9), Homing Attack (13), Wall Jump (39/40), Slide (41), Crouch (43), Ground Pound (44).
- The full Game Land speed_get, speed_set and speed_ui C2 group remains installed. Grand World Map refresh remains omitted for available space.
- New `controller_identity_mode: exact_host_authenticated_controller_per_stage` and `controller_arm_reason` status fields. Cumulative telemetry remains.

## Safety and remaining unknowns

- V7 is a **test**, not a demonstrated permanent fix. It deliberately fails open when the controller is questionable, so an ability may temporarily be available immediately after a level load. New actors might still take alternate native request paths not covered by the hook. User should report actual gameplay results and the **delta** in denial/authentication counters, not only absolute counter values.
- V7 does **not** repair corruption caused by older V4/V5/V6 sessions. Perform a **full cold restart of Dolphin** and do not load snapshots made in the corrupted sessions.
- Separate `Swim` and `Breath` items remain in the AP schema, but there is no proven native underwater-jump or oxygen-timer lock. `/sonicwater` remains read-only.
- A proper end-to-end proof requires live Act 1 > Act 2 > Act 1 gameplay tests with before/after commands. If native state fields again become implausible, collect synchronized MEM1 and MEM2 captures at the affected stage, preferably just before and after the scene switch.

## Offline tests

- `offline_tests/test_request_gate_v7.py` executes generated PPC against 1056 stage/state/ownership scenarios, including observed corrupted raw state words.
- `offline_tests/test_revision_sim.py` verifies original `main(4).dol`, C2-modified DOL and mutable guest telemetry all normalize to correct original PAL hash.
- Gecko footprint: 3240 / 3256 bytes. Never add this group to a previous experimental group.
