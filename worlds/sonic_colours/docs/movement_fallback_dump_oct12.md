# Sonic Colours PAL: Double-Jump stuck in Ball Form (2026-10-12)

## Verified memory evidence (PAL SNCP8P revision 0)

- Uploaded stuck-in-ball dump `mem1(20261012-022012).raw` / `mem2(20261012-022021).raw` has native movement controller `0x80B58A40` (vtable `0x8075FA3C`), `controller+0x5c = -1` (transition sentinel), `controller+0x60 = 8` (Double Jump). Same stage/player owner chain as previously studied. `-1` alone can be legitimate for one frame; the user independently reports it remains stuck.
- Older vanilla idle `mem1(20261011-160037).raw` has `2,2` (Stand); older vanilla Double Jump `mem1(20261011-160319).raw` has `8,8`. Heap pointers differ between sessions; never hardcode them.
- Original PAL DOL disassembly: `0x80033188: lwz r0,0x20(r31)` then `0x8003318c: stw r0,0x1c(r31)`. At `0x80033190..0x800331E8` the engine performs state-object lookup, callbacks and potential fallback. The old C2 deny branch redirected to `0x800331EC`, **skipping this native initialization**. This explains why the requested Double Jump could be blocked without the state manager recovering from `-1`.

## Experimental C2 replacement

- Retains verified player+controller ownership and independent seven-item AP bitmask.
- For a denied transition, the PPC stub increments a **guest-only denied-transition counter**, records the attempted state ID, and changes the *pending* target to an existing native state. The original `lwz r0,0x20(r31)` and **entire original transition/initialization sequence** execute normally; no manual write to the current-ID field.
- Temporary fallback: `CStateStand` ID 2 for denied crouch 43 / slide 41; `CStateBallJump` ID 7 for denied Double Jump 8, Mid-Air Boost 9, Homing Attack 13, Wall Jump 39/40 and Ground Pound 44. The validity of these contexts is **not** live verified; particularly wall interactions and airborne behavior can still glitch. The preferred ultimate solution remains ability-specific input eligibility before state-transition side effects.
- Extra C2 mutable diagnostics: `denied_transition_count`, `last_denied_state`, `guest_denial_counter_nonzero` shown in `/sonicmovement`. If you attempt Double Jump without the item, look for `last_denied_state: 8` and an incrementing hit counter. `native_gate_verified` remains false until game-behavior confirmation.
- Gecko total: 3152 / 3256 bytes. Original profile *must be fully replaced*, never stacked with prior codes. Original save/intro/White Boost code inherited from No-Slot Gecko Controls V2. AP item IDs and schema 7 unchanged.

## Offline tests performed

1. Big-endian MEM1 pair comparison for stuck, vanilla Double Jump, idle.
2. Test of the original PAL DOL dispatcher at 0x80033188..0x800331EC.
3. Independent minimal PPC interpreter with 8 denied states, 8 owned states, 8 owner-mismatch cases, 10 unrelated vanilla states. Ensures native pending request is written only when denied and the stub returns to the original trampoline, not to 0x800331EC.
4. Gecko C2 branch, header length, exact payload recognition, return, and guest-mutable telemetry validation (corrupting PPC instruction causes fail-closed).
5. Full Gecko byte count against codehandler capacity; direct RAM sandbox capacity checked but **not recommended** for use.

**This is not a Dolphin live verification. Do not claim full movement lock functionality, especially Swim/Breath.**

## Installation and first live test

1. Stop Dolphin and all Archipelago processes; do **not** continue a Savestate taken during the glitched transition.
2. Replace `custom_worlds/sonic_colours.apworld` with the matching new fallback APWorld. Never mix a duplicate unpacked world with the zip.
3. Replace the **entire** old movement Gecko profile with `SNCP8P_Movement_Fallback_TEST.ini` (its `[Gecko]` and `[Gecko_Enabled]` blocks); do not combine with the original four-group codes.
4. Enable cheats and select only the replacement profile. Restart emulation from a safe game save with the same schema-7 seed.
5. Start the client normally (NO `--experimental-direct-hooks`). In Tropical Resort Act 1 execute `/sonicmovement`, check `owned_mask: 0` and `denied_transition_count: 0`.
6. Try one Double Jump, observe ball animation and ability failure. Run `/sonicmovement`: the C2 hit counter should be >0 and `last_denied_state: 8`; `current_id` should recover from -1. If Sonic still sticks or Dolphin throws invalid read, stop and capture both MEM1 and MEM2 dumps.
7. If the transition recovers cleanly, obtain the Double Jump AP item and repeat; count should **not** increase for authorized state 8, and native Double Jump should work.

**Live safety**: The previous Gecko profile's denied transition is proven structurally broken. Never re-enable it for movement tests. Use backups. The new fallback is still speculative; especially wall-jump and homing may need upstream gating.
