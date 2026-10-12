# Sonic Colours PAL: Movement Request Gate V5 (stage-lifecycle telemetry)

**Status:** Experimental diagnostic, NOT a confirmed fix for the level-change regression. This build preserves V4's native request-cancellation algorithm at `0x8003388C`. The only changes are authenticated C2 guest counters and clearer read-only state diagnostics. `Swim` and `Breath` still have no functional native hook.

## Dolphin evidence prompting this build

- New Game Tropical Resort `stg110`: native controller `0x80B58A40`, denied count `0`, user reported early movement locks worked.
- After entering `stg130`: native controller `0x80B50780`, cumulative denied count `205`, last denied state `13`. `requested_id=1065353216 = 0x3F800000 (float 1.0)` is NOT a plausible native state ID. Do not treat it as a real ability/state transition.
- After returning to `stg110`: controller `0x80B62C40`, cumulative denied count still `205`. This is not proof the hook is inactive: the captured sample may contain no subsequent denied request.
- Runtime V4 already reconfigures `controller` whenever a new living Sonic and a changed controller are observed. Avoid claiming a fixed cached controller without further evidence.
- The client is bound to an attributed save in the last log; the separate AP save/prologue binding is no longer the primary suspect.

## Telemetry (all guest counters start from cold boot and never reset on load)

`/sonicmovement` now contains:

- `total_request_handler_entries`: number of C2 invocations at `0x8003388C`, including non-Sonic state-machine instances.
- `sonic_controller_authenticated_requests`: those invocations which passed all exact Sonic actor/controller ownership checks. THIS is the crucial stage-reload signal.
- `denied_transition_count`: authenticated calls whose requested movement item was absent.
- `last_authenticated_request_id`: most recent requested state ID from the verified Sonic controller.
- `last_handler_controller_seen`: controller candidate from the last request, MAY belong to a foreign state machine. Never use this as an address to write.
- `requested_id_hex` and `state_fields_plausible` on the player controller read-only snapshot, to flag float-bit-pattern or corrupt/nonstandard observations.

The counters are global to the installed guest thunk and cumulative since Dolphin cold boot. Only calculate **deltas** between readings in the SAME session. They do not prove gameplay quality or successful denial by themselves.

## Minimal differentiating test

1. Back up your save. Replace BOTH APWorld and Gecko profile, and FULLY restart Dolphin. Do not combine previous V3/V4 profiles or enable direct hooks.
2. With `movement_unlocks: true`, no relevant movement items, and `owned_mask=0`, enter Tropical Resort Act 1. Run `/sonicmovement`, record the five counter/target fields. Attempt a single Crouch. Observe whether it is blocked and whether Sonic can stand/move normally. Run `/sonicmovement` again.
3. Change to Act 2. Once fully in gameplay and `/sonicmovement` shows the new controller, record counters. Attempt the SAME unavailable movement and read again. Repeat once after returning to Act 1.
4. Determine the branch:
   - Handler entries increase, authenticated requests do **not**: the native controller ownership chain / actor identity differs after reload; collect a new MEM1+MEM2 pair **while trying the ability**. Do not weaken ownership checks.
   - Authenticated requests increase but denied requests do **not**: different state target/permission bit or prior state `-1` escape path; use `last_authenticated_request_id` and the read-only state fields.
   - Denied requests increase but movement still executes: the request hook is insufficient (alternate native path or upstream action effects). Stop stacking state hacks; trace the ability-specific permission/input call sites.
   - All counters flat: this control flow is not reached in that new stage; trace alternate state-request entry points.
5. If a movement freezes, causes invalid read or broken physics, stop, record the log and dump, and fully restart Dolphin before using another profile.

## Authenticity/safety

The PAL SNCP8P Rev0 DOL site and full revision fingerprint remain validated. Gecko C2 installation must be recognized exactly including the newly allocated 32-byte mutable mailbox (first two words written by host, next six by guest). The host still authenticates the current Sonic actor/controller; the guest does not trust pointers from the telemetry. All PPC registers and condition bits used by the hook are preserved, and the original request routine is rejoined as in V4. The Gecko footprint must remain at most 3,256 bytes. These are offline properties only.
