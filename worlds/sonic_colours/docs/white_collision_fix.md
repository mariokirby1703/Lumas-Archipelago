# White capsule collision reactivation

Live test on October 11, 2026, PAL SNCP8P, mandatory Tropical Resort Act 1:
the user confirmed White was absent and Boost Lock enabled. Status reported
White denied and the capsule appeared inactive. Receiving White Boost Wisp
changed ownership and made the same capsule appear without restarting, but the
user could not collect it by contact.

Read-only DME observation matched the same unopened actor `0x90FC19E0` and
existing collision wrapper `0x90FC1E00`. The available model was mode 1, state 1,
but the collision wrapper's enabled byte at +0x54 remained 0. No guest memory
was manually altered in this investigation.

PAL ghost entry at `0x800D55AC` invokes `0x800D517C(actor, 0)`. This routine
passes the enable argument to `0x800812B8` for each existing body. The previous
AP refresh created a body only if absent and restored the model/lifecycle, but
did not re-register an existing disabled body.

The updated C2 payload invokes `0x800D517C(actor, 1)` after model/body setup,
before the native available-state transition and specialized lifecycle selection.
It preserves native body ownership, physics registration and state-specific gates;
there are no host writes to collision flags. Matched available capsules and opened
capsules retain their existing lifecycle. White and all seven regular coloured
capsules exercise the same native registration call. The exact previous White
payload remains recognized, including its guarded mutable ownership data; status
reports `collision_reenable_installed: false` for it and true for the new payload.

Offline validation: 37 capsule/runtime/packaging tests and 101 memory/gameplay
control tests passed. The PPC tests cover an existing disabled body, all colours,
White's signed -1 type, no duplicate allocation, opened capsules, revocation and
ABI preservation. They explicitly stub native calls and do not prove contact
collection or gauge delivery.

Install the newly built APWorld and replace the capsule Gecko group with the
updated repository INI, then restart client and emulation. The installation
workflow remains unchanged. Live acceptance still required: deny White in a
fresh intro, receive the AP item beside the capsule, touch the same refreshed
capsule, verify opening/check acknowledgement, then collect released White Wisps
and verify the gauge fills and Boost works. The pre-fix visible refresh is live
verified; see the subsequent successful live test below.

## Successful post-fix live test

On October 11, the updated 928-byte C2 payload was read back and matched
`current_white_collision_refresh` exactly in Dolphin, returning to `0x800D4828`.
In the fresh mandatory `stg110` intro, the capsule was initially a denied ghost
with its collision-wrapper enable byte 0. After receiving White Boost Wisp over
AP, the user confirmed successful contact opening and collecting the released
Wisps for the Boost gauge, without an Act restart. A subsequent read-only native
snapshot measured Boost **35.0 / 100.0**, previously **0.0 / 100.0**; the consumed
capsule was no longer present in the enumerated capsule list.

This validates the White lock/refresh/contact/gauge-delivery sequence for the
first Tropical Resort Act 1 capsule with the fix from commit `71b80843`.
The user subsequently confirmed that pressing Boost works after the unlock.
A capsule LocationChecks acknowledgement, all coloured capsule types, later
Acts and restart persistence were not established by this observation. The
138 offline tests remain separate evidence.

## Cyan live test in the same mandatory intro

The user next stood beside locked Cyan capsule object 23 in `stg110`.
Read-only pre-unlock observation: native colour 1, unopened ghost model mode 0,
state -1, no collision body, stage/actor-state permissions 0 and held Wisp -1.
After receiving Cyan Laser Wisp through AP without restarting, the user confirmed
the requested appearance, contact opening and Laser transformation test worked.
The subsequent snapshot measured stage and actor-state permissions **2** (Cyan
bit), and a later Cyan capsule (object 93) had available model mode/state 1 and
a collision body. An unowned Yellow Drill capsule remained a ghost without a
body. The originally tested Cyan actor was no longer enumerated after moving on.
The transformation itself is user-observed; this later snapshot was already back
in normal player mode with no held Wisp. Capsule AP acknowledgement and other
coloured transformations remain unverified by this test.

## Reward delivery observations

In the same live test session, the user confirmed repeated Rings and 1-Up
deliveries worked, followed by Ring Loss Trap and a subsequent Rings delivery.
The user also confirmed that Rings, 1-Up and Boost Refill received during the
results-screen deferral test were successfully held and delivered afterward.
These are user-observed gameplay results. Individual HUD deltas, receipt indices,
receipt logs and restart/reconnect during deferral were not captured; therefore
this session does not establish exactly-once delivery across a process restart.

In a subsequent targeted test, the user confirmed the requested sequence:
receive a 1-Up on the results screen, close and reconnect the AP client while
Dolphin continues running, then enter the next Act. The deferred life arrived
once as requested. This is user-confirmed restart persistence for that 1-Up;
receipt logs and independent before/after counter captures were not supplied.
