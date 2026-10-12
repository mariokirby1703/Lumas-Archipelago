# Sonic Colours (SNCP8P Rev0) early movement-request Gecko C2 V4 (experimental)

## Confirmed Dolphin findings from user
- Previous C2 at `0x80033188` denied Double Jump but froze actor with current `-1`, requested `8`.
- Fallback V3: crouch attempted while `owned_mask=0` advanced `denied_transition_count` from `0` to `7`, `last_denied_state=43`, yet Sonic stayed in crouched animation. After Ground Pound, the counter was `15`, `last_denied_state=44`, and Sonic was stuck in a stomp. Double Jump was still visually possible even without an item.
- These observations confirm PPC C2 execution and deny detection but **not** correct ability suppression. They disprove the V3 fallback as a safe gameplay lock.

## Earlier native hook was too late
Original PAL `0x80033040` function calls native state callbacks at `0x800330F0..0x80033180`, **before** `0x80033188` transfers pending state into the current ID (`lwz r0,0x20(r31)` / `stw r0,0x1c(r31)`). The late V2/V3 hook therefore cannot cleanly prevent an already-initiated transition or rollback physics/animation state.

## New gate at native state-request function
Disassembly of the exact original PAL DOL identifies `0x80033878` as a common request handler (364 direct branch-and-link references in text sections). Its instructions are:

```asm
80033888: mr r31,r3
8003388c: lwz r0,0x20(r3)   ; hook here, original instruction retained
80033890: cmpw r4,r0       ; r4 = incoming target state ID
80033894: beq 0x800338a8 ; unchanged state request => clean return
80033898: addi r3,r3,0x14
8003389c: bl 0x800395b0  ; state-changing callback handler
```

V4 authenticates the exact live controller, Sonic actor and controller VTables, then compares incoming `r4` with the eight gated IDs. When an AP permission is missing, it increments an in-guest counter and copies the old pending state `*(r31+0x20)` into `r4`. Original instructions then run and take their native no-op return. **No memory field and no fabricated fallback state are written.** When the prior request equals `-1` (uninitialized), do not suppress a state request. This avoids preventing initialization and respawn, but ability restrictions at that instant remain unverified.

This is **not Dolphin-live-verified**. Early state requests could still be preceded by input/animation setup elsewhere, or alternate request paths could exist. Scripted state requests in Sonic's own controller may also hit the gate, requiring future call-site filtering. Validate one action at a time on a disposable save, restart Dolphin completely after any hang, and never combine old and new Gecko code groups.

## Expected live diagnostic
`/sonicmovement` should show `armed EARLY native movement request-gate experiment via Dolphin Gecko C2`, count initially 0. Try Crouch without item once: expected counter advances, `last_denied_state=43`, Sonic should remain in the preceding normal state without stuck animation. Then try Ground Pound (`44`) and Double Jump (`8`) separately. **Actual gameplay is the acceptance test.**

Swim and Breath remain distinct AP items **without native gates**. The 7 underwater captures did not prove a safe oxygen variable/bubble refill hook. Do not assert they work.
