# Sonic Colours PAL SNCP8P Rev0: Boost / Movement V10 TEST

**Status: offline-verified experimental. No live Dolphin execution performed in this package.**

## Inputs from the live V9 tests (2026-10-12)

- New Game, Tropical Resort Act 1: `white_boost: false`, `temporary_boost: false`, `boost: 35.0` after an enemy kill.
- `native_gameplay_controls.boost_lock_active: false`, while `boost_gain_guard.status: "deferred: boost provider pointer unavailable"`.
- At stage start, the original native player chain *does* expose the boost object via player/stats; the no-selected-save branch in `NativeHooks.snapshot` failed to copy `boost_address` and `boost_max_address` into `Snapshot`. Other branches did copy both.
- Movement: initial Act 1 successfully denies requests; Act 2 and later stages show pointer/float-like words as `current_id`/`requested_id`, and host sets `controller: null`, even while the stage actor/owner and canonical controller vtable/backreference can be checked.
- Observed live values for the *experimental* controller state fields include `0x92EAC334` and `0x36C9D89C`. They MUST NOT be interpreted as movement-state IDs.

## Boost fix

`client/hooks.py` carries the exact vtable-checked live boost provider and maximum addresses into an unsaved, attributed intro snapshot. Existing `Runtime.enforce_white_boost_gain_lock` then clamps vanilla enemy/script gains when White Boost Wisp is missing:

- No White and no receipt-backed AP Boost: the legitimate ceiling is **0**. Any observed positive gauge value is clamped to 0 via the existing guarded `boost_stats` write policy.
- `Half Boost Refill`/`Full Boost Refill`: the client records one receipt-backed ceiling, allows consumption, and never increases that ceiling because of enemy kills.
- White owned: normal vanilla meter filling is allowed.
- `boost_lock` option off: do not enforce any boost restrictions.

**Important limitation**: This fallback runs on the client polling interval. A momentary visible fill may precede the clamp. It does not prove that a second native reward path was patched, nor does it preclude further native opponent reward research.

## Movement experimental V10

The earlier V8/V9 early hook at PAL `0x8003388C` is a generic native state-machine request dispatcher (`0x80033878`), **not** a Sonic-exclusive function. It must never deny another actor's requests.

The existing exact player-controller equality and native vtable/backreference requirements remain. In V9 the hook tested `controller+0x5C/+0x60` as state IDs and the host refused to arm when those were pointer-like. These offsets are not proven state IDs across acts.

V10 changes:

1. The host still resolves Sonic through the validated player actor chain and verifies controller vtable and `controller+4 == player` on every poll. It arms after 3 stable polls for plausible host state values, or **10 stable same-stage actor/controller polls** when the experimental state fields are implausible.
2. The guest hook no longer treats `controller+0x5C/+0x60` as universally valid IDs. Instead it reads the **original PAL request predecessor** at `r3+0x20` (corresponding to the displaced `lwz r0,0x20(r3)`).
3. A denial is allowed *only* if this original native predecessor is within `0..127`, the exact host-authorized controller is the handler owner, the controller vtable matches, the requested target state is a known locked move, and the relevant AP item is not owned. Unknown/negative/pointer-shaped native predecessors fail open.
4. The hook records `last_handler_native_previous_hex` and a plausibility flag even on handlers that do not authenticate as Sonic, alongside the existing cumulative counters.
5. No forced `Stand`, `BallJump`, or post-transition jump that skips native initialization; denied requests remain a no-op within the original request flow.

This is a **hypothesis-driven Live TEST**, not a confirmed final movement solution. It is entirely possible that, after the stage change, the native request predecessor is also pointer-like, that the relevant request is sent through another state machine, or that the `r31-0x40` identification assumption is stage-dependent. If so, the hook must *not* deny the movement and proper Act-2/ Game Land MEM1+MEM2 snapshots are needed to find the real per-stage owner/request identity. The guard intentionally prefers temporary loss of locking to state-machine corruption.

`Swim` and `Breath` remain independent AP items **without implemented native underwater movement/oxygen restrictions**. Do not interpret `swim_gate_verified` or `breath_gate_verified` as successful. Normal breathing vs the desired 10-second countdown still requires oxygen timer/air bubble reverse engineering.

## Offline verification

- Mock unsaved PAL snapshot from an attributed native intro actor with 35 gauge and no White or AP receipt: native boost addresses must be retained, and the guard must clamp to 0.
- Boost-gain guard receipt, consumption, White-owned, disabled option, invalid actor tests.
- 474 PPC micro-execution scenarios covering all locked state targets, three controller addresses, missing and present items, mismatched owner, pointer/float previous words, and unrestricted moves.
- Original SNCP8P PAL DOL SHA256 tested with genuine-style C2 hook installation and mutable guest telemetry/control data.
- Act1 -> Act2 -> Act1 stage actor rearming and garbage host state field regression.
- Combined replacement Gecko payload size `3224/3256` bytes. **V10 INI must replace all previous movement Gecko C2 groups.** Game Land speed controls remain included.

## Live test order

1. Fully close Dolphin and Sonic Client. Back up saves. Replace APWorld and **all** Gecko V8/V9 groups with **one** V10 Gecko profile. Restart Dolphin fresh with cheats enabled, run the PAL SNCP8P Rev0 game and matching Schema 7 seed. Do not use `--experimental-direct-hooks`.
2. In New Game Act 1 before receiving White, record `/sonicstatus` showing `native_gameplay_controls`, `boost_gain_guard`, `boost`, `white_boost`, `temporary_boost`. Kill one enemy. Record again 1-2 seconds later. Desired: Boost returns to 0, white false, and the guard status indicates a valid gauge/clamp rather than `provider pointer unavailable`.
3. Act 1 without movement items: run `/sonicmovement`, try Crouch or Double Jump, compare denied counters. Do not continue if Sonic is stuck; no savestates from failure.
4. Act 2 after waiting a few seconds: run `/sonicmovement` before/after exactly one forbidden action. Report handler counter deltas, authentication/denial counter deltas, `controller_arm_reason`, `last_handler_controller_seen`, `last_handler_native_previous_hex`, and whether the action was prevented. Return to Act 1 and repeat.
5. If stage-2 native predecessor is pointer-shaped or handler ownership does not match, capture MEM1 and MEM2 **in Act 2 while Sonic is idle (stable 5 seconds)**, then while performing the move (paused or frame-advanced). Include matching `/sonicmovement` output. Do not infer a new hook solely from guessed controller offset.
6. Game Land speed UI is present in the code list. Separate visual/current-speed test still required.

This build preserves the Schema 7 item IDs, item options, and seed structure. No new seed or APWorld generation is needed for an existing compatible Schema 7 seed. This release is not a Dolphin-tested production client.
