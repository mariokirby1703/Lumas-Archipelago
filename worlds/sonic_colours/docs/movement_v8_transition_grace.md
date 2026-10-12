# Sonic Colours PAL SNCP8P Rev0: Movement V8 Transition Grace

**Status: experimental. Offline PPC tests passed. Dolphin live behavior NOT verified.**

## Evidence from user's V7 gameplay

- Act 1 controller: `0x80B58A40` with `owned_mask: 0`.
- `denied_transition_count` rose from 59 to 117 while user attempted various actions.
- Paused-frame `/sonicmovement`: `current_id: -1`, `requested_id: 3`, `state_fields_plausible: true`.
- Yet V7 status: `movement hook fail-open: invalid/uninitialized controller state; fail open`, `controller: null`.

The V7 host demanded `current_id >= 0` despite the reader permitting `-1`; its PPC gate did an *unsigned* comparison against 127, also excluding `-1`. Both opened native movement permissions during a normal transient state. Input spamming could exploit the window.

## V8 changes

1. **Host** permits `current_id == -1` only if: exact controller address, exact player actor, and exact stage epoch already had a stable authorized sample; `requested_id` is 0..127; scene gameplay/alive/verified and three stable polls are still required.
2. **Guest PPC** normalizes current state by +1 before an unsigned <=128 check. This recognizes exactly `-1..127`, but rejects all other negative integers and floats/pointer patterns seen in earlier dumps.
3. The guest still refuses to suppress native initialization if the **previous pending request is `-1`**; the host also fails open on new/unattributed controllers, loading, different stage epochs, corrupted states, or dead Sonic.
4. Read-only `/sonicmovement` telemetry adds `transient_minus_one_grace_active` and `controller_arm_reason`.
5. No changes to item IDs, schema, Wisp/music logic, Game Land speed controls, or swim/breath behavior.

## Tests and limitations

- `offline_tests/test_request_gate_v8.py` executes real encoded PPC instructions in a small stand-alone emulator (432 action/state/actor cases, corrupt-pointer exclusions, previous -1 exception).
- `offline_tests/test_configure_epoch_v8.py` simulates exact stage/actor/controller ownership across transitions, loads, and recycled heap controller addresses.
- `offline_tests/test_revision_sim.py` checks the original PAL DOL hash, Gecko C2 payload, and mutable control/telemetry signature normalization.
- Gecko profile: 3240 / 3256 bytes, **REPLACES** V7 / V6 / standard Gecko groups.

**Unresolved**: A denied request may still be initiated by a different native code path; earlier game-state corruption at level reload also remains possible. Running in Dolphin is essential. Native Swim/Breath still unimplemented. There is no guarantee every action is fully locked.

## Controlled test

1. Backup saves, cold restart Dolphin, replace APWorld + Gecko profile and activate only new groups.
2. Stand still in Act 1 for stable authorizations. Query `/sonicmovement`.
3. While still in Act 1, try crouch and double jump without their items. Count denials and see whether the action visibly starts.
4. If safe, repeat rapidly and pause during one action. With an already authenticated controller, `current_id=-1` should **not** clear `controller` and the status should report `transient_minus_one_grace_active: true` when the poll catches it.
5. Enter Act 2; expect stage epoch rearm delay, not indefinite authorization from the old controller. Compare counter deltas.
6. If Sonic sticks or Dolphin flags invalid read, STOP; send logs + paired MEM1/MEM2 dump. Do not keep playing from corrupted Savestates.
