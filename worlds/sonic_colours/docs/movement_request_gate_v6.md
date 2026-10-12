# PAL SNCP8P Rev0: Movement Request Gate V6 / Game Land Speed Restoration

**Experimental: not a Dolphin-live-verified fix.** This build replaces V5. Never combine the V5 and V6 Gecko entries.

## What the user's V5 log proves

- `stg110`: controller `0x80B58A40`, total handler entries 231, Sonic-authenticated 228, denied 50, last denied 8.
- `stg130`: controller `0x80B4C040`, handler entries 303, Sonic-authenticated 276, denied 51, last denied 9.
- Back in `stg110`: controller `0x80B473C0`, handler entries 521, Sonic-authenticated **still 276**, denied **still 51**. The handler was called 218 additional times with no newly authenticated Sonic requests.
- After returning, `owned_mask` had changed to 1, **not zero**: Double Jump (bit 0) was received. Do not use Double Jump alone for a denial test after receiving that item.
- The status reader once observed an implausible movement current ID (`919163804`), so do not interpret all read samples as valid native state IDs.

These facts prove a lifecycle/ownership mismatch in the request hook's authentication and distinguish it from Gecko not executing. They do **not** prove that an old controller pointer was retained in the host mailbox; V5 already re-arms it based on current gameplay observations.

## V6 changes

1. Instead of trusting a single heap controller address embedded in Gecko, the host's pointer now **arms or disarms** the hook only. At each request, the guest validates the current receiver's native controller vtable `0x8075FA3C`, its player `+4`, player actor vtable `0x8075AEF8`, and the back-reference at player `+0x90`. This allows a newly constructed Sonic controller to be authenticated during stage load/reload even before the host has updated the exact previous address. A foreign actor still fails authorization. This is a more permissive actor policy and needs genuine Dolphin tests, especially respawn and cutscenes.
2. An exact 48-byte lookup table maps gated native state IDs to AP permission bits: Double Jump 8/bit0, Jump Dash 9/bit1, Homing 13/bit2, Wall Jump 39+40/bit3, Slide 41/bit4, Crouch 43/bit5, Ground Pound 44/bit6. States not in the table remain vanilla. This shrinks the payload while retaining its native denial and entry/authenticated counters.
3. Restores Gecko `speed_ui` at `0x802EEB10`, **in addition** to `speed_get`/`speed_set`. These three original native speed hooks are required to consistently restrict speed tier selection/display/application. Game Land Speed is still governed by the corresponding AP items. `speed_controls_active` should now be true after successful configuration.
4. Original hook `0x8003388C` still changes a denied state request to the previous request before the game's own compare/return. It never rewrites current state or shortcuts the native state transition initialization.
5. `Swim` and `Breath` remain AP items **without** a safe native underwater jump/oxygen implementation. Their absence from native lock handling is explicit.

## Safety and scope

- Internal 3256/3256 Gecko bytes including all speed hooks, original capsule/white boost, progression, and Eggman Heart hooks. Grand Map refresh remains omitted; this test profile is not the all-features release.
- Controller and item mask are still installed via exact readback/revalidation, with controller written last; first word zero makes native gate a no-op.
- The table is static, outside the guest-mutable 32-byte mailbox. The installed C2 body and PAL DOL text hash are verified against the original SNCP8P Rev0 executable.
- Offline PPC micro-execution passed 288 combinations of gated state, owned/missing item, valid/foreign player, controller identity and previous state. The original PAL hash normalizes correctly with this C2 installed and when guest counters/mask change. This is **not** an end-to-end Dolphin test.
- **Known limitation:** this dynamic actor authentication does not prove the stage's active actor pointer; the live experiment must verify it does not accidentally gate scripted/demo Sonic objects. On crashes or stuck animations stop, do not continue the same savestate.

## Test procedure

1. Back up saves. Quit Dolphin and client entirely. Replace the APWorld and **both** game-specific `[Gecko]` / `[Gecko_Enabled]` sections with this V6 file. Do not append or co-enable older profiles.
2. Cold-start Sonic on PAL SNCP8P Rev0 with Cheats ON. Start client normally (no `--experimental-direct-hooks`). Existing schema 7 seed with `movement_unlocks: true` can be reused; the new payload has no item/slot schema changes.
3. Read `/sonicstatus` and `/sonicmovement` inside Tropical Resort Act 1. `movement_unlocks.status` must mention V6; `installed_signature_verified: true`; record all cumulative counters and owned_mask.
4. Attempt one missing movement (prefer Crouch if no Progressive Crouch item) and compare counters. The key check is that deny counter increases and Sonic returns to normal movement, not just that the signature exists.
5. Switch to Act 2; run the *same absent-item test*, then return to Act 1. Compare changes in `total_request_handler_entries`, `sonic_controller_authenticated_requests` and `denied_transition_count` between reads. A physically playable level with no authenticated increments indicates that this earlier request routine may not be the active movement path for that stage.
6. At Game Land's speed selection menu, verify that higher tiers are unavailable with zero Game Land Speed items and unlock progressively (the displayed choices and actual selected speed). Check `native_gameplay_controls.installed.speed_ui` and `speed_controls_active` in `/sonicstatus` first.
7. If available, send `/sonicmovement` before and after each test and the Game Land speed screen/result. **Do not infer live success from offline tests.**
