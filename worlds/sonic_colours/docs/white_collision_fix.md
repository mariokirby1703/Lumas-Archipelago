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
verified; post-fix collision registration and collection are not yet live verified.
