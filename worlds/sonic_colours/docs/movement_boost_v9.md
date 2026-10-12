# PAL Sonic Colours Wii AP: V9 Boost gain guard + movement stage rearm

## Scope

Compatibility: original PAL SNCP8P Rev0, Schema 7. This package does **not** introduce new items, option IDs, or Gecko payloads. It reuses the complete V8 Movement Transition Grace Gecko profile, including the Game Land speed UI C2.

### White Boost without the AP item

`boost_add` C2 already attempts to block native positive gains. The V9 runtime adds a **backup meter ceiling** after every successful live snapshot, before applying new AP item receipts. With Boost Lock enabled and no `White Boost Wisp`, normal native boost gains (including enemy rewards which bypass the hooked add path) are clamped back to the current **AP-authorized remaining balance**. By default this ceiling is zero. A Half/Full Boost Refill **receipt** writes the amount and records a contextual ceiling after verified native write. Once Boost is spent, the authorized ceiling falls. Vanilla gains cannot raise it again. The grant is scoped to the same native actor/stage and Dolphin process; an old journal cannot be used to authorize a new actor/seed. With White owned, the guard is inactive and vanilla gains are unrestricted.

This is a **client polling correction**, not an inline PPC interception of every enemy reward. The meter may visually rise for a fraction of a second until the next poll. If the client cannot attribute a live actor, it does not issue a speculative write. A zero ceiling with Boost Lock enabled is intentionally stricter than a temporary refill: enemy gain is never permission.

### Movement after act reload

The V8 **request gate itself is unchanged**, retaining its reported ability denial counters and strict exact-controller identity. V9 changes the host arm sequence: a fresh controller needs three consecutive stable, valid, attributed observations in the same stage epoch before it is armed. The hook remains de-armed during loading and on invalid pointer/float state fields. Native `current_id = -1` remains tolerated **only** during a transition of an already-authenticated same-stage actor. The new `/sonicmovement` field `stage_controller_consecutive_samples` makes rearm timing visible.

This attempts to avoid interfering with early level-init transitions and cannot guarantee that every movement goes through the same request handler after level reload. State requests which go through other paths or a persistently malformed controller remain unresolved. **It is not a verified complete movement fix.** Swim/Breath gates remain research-only and absent in this build.

## Tests in this deliverable

- `offline_tests/test_boost_gain_guard_v9.py`: no-White enemy gain; legitimate refill; consumption; spent refill; other stage; White unlock; disabled Boost Lock; scene guard.
- `offline_tests/test_stage_arm_v9.py`: stage first/second/third snapshots; loading; new actor; transient -1; corrupted state.
- `offline_tests/test_request_gate_v8.py`: 432 PPC scenarios, unchanged payload.
- `offline_tests/test_configure_epoch_v8.py`: actor/epoch isolation; unchanged transient-grace behavior.
- `offline_tests/test_revision_sim.py`: original PAL DOL SHA normalization and modified mutable data verification.

Obsolete V6/V7 historical tests deliberately assert their old hook layouts; do not run those against V9 as a global `pytest` suite. Tests do not replace Dolphin hardware/emulator gameplay verification.

## Live tests

1. Stop Dolphin and client, back up your save. Replace `sonic_colours.apworld` under `C:\ProgramData\Archipelago\custom_worlds` with this V9 build. **Keep the V8 Gecko INI enabled and unchanged**; do not simultaneously load the source tree world.
2. Cold-start Dolphin, start PAL game, connect the matching Schema 7 seed with `boost_lock: true`, `movement_unlocks: true`.
3. Before killing an enemy without White, run `/sonicstatus`. Watch `boost`, `native_gameplay_controls`, and `boost_gain_guard`. Kill one enemy, wait 1-2 seconds, run `/sonicstatus` again. The current gauge should settle at zero unless an AP refill still has authorized remaining balance.
4. When granted Half/Full Boost Refill, check that Boost fills, can be spent, and defeating subsequent enemies **cannot increase the balance**. After receiving White Boost Wisp, native enemy gains must again work.
5. For Movement, take `/sonicmovement` before/after an unowned Crouch or Double Jump in Act 1, Act 2, and after returning. Compare counters as *deltas*. The `stage_controller_consecutive_samples` should reach 3 each time while living in stable gameplay. If gameplay locks fail or Sonic gets stuck, stop, record statuses and (if available) MEM1/MEM2 dumps.

No live Dolphin claims are made for V9.
