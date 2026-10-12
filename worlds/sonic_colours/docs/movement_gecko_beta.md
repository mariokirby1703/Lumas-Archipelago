> **Superseded for movement tests (2026-10-12):** The old Gecko C2 deny branch skips native transition initialization and was observed to stick Sonic in Ball Form (controller -1 -> 8). Do not use the old movement profile. See [Movement Fallback TEST](movement_fallback_dump_oct12.md) for the experimental replacement.

# Sonic Colours Wii PAL: Movement Gecko BETA (2026-10-11)

**Experimental, no Dolphin gameplay execution confirmed.** Correct target is
`SNCP8P`, PAL revision 0, original DOL SHA256
`92aefe33b577493b492f8433ca68b90d25d29d2d6f9c85310a6829481281f8a9`.

## What is delivered

A **replacement** Dolphin Gecko INI named `SNCP8P_movement_gecko_beta.ini`.
It is not an addon. It is calculated from the existing 4-group production
Gecko export, then drops the `grand_map_refresh` hook at `0x80266410` and
`speed_ui` at `0x802EEB10`. They are removed to fit a native Movement C2 at
`0x80033188`, inside the standard Gecko codehandler's 3256-byte budget.
It retains the capsule, story progression, boost use/query/add, speed get/set,
Eggman Hearts and both map transition hooks. Music continues using the verified
MEM2 bank, unaffected by this change.

Movement hook has two mutable words: the live controller pointer (armed last),
then the AP-owned permission mask. The host authenticates the exact byte-level
C2 payload, the PAL executable, current living Sonic actor and controller before
writing only those two transient hook words. A `0` controller disables the
identity match. No permanent save flags are touched by this specific writer.

The previous erroneous PowerPC `andi.` argument order was corrected:
`andi. r9,r10,bit` (RS=10, RA=9), NOT `andi. r10,r9,bit` (RS=9, RA=10).
This preserves r10's mask across eight state comparisons. The relocatable
Gecko deny branch uses absolute CTR transfer to the original safe post-switch
continuation `0x800331EC`; the normal path executes displaced instruction
`lwz r0,0x20(r31)` and returns through the Gecko-generated branch.

| AP item | Native states potentially denied without item |
| --- | --- |
| Double Jump | 8 |
| Mid-Air Boost (Jump Dash) | 9 (independent of White Boost/ground boost) |
| Homing Attack | 13 |
| Wall Jump | 39 and 40 |
| Ground Pound | 44 |
| Progressive Crouch x1 | grants Crawl 43 |
| Progressive Crouch x2 | also grants Slide 41 |
| Swim | item exists; **not native-gated yet** |
| Breath | item exists; **not native-gated yet** |

## Installation for testing

1. Back up Dolphin save files and your existing `SNCP8P.ini` or active Gecko
   configuration. Close Dolphin and every Sonic Client.
2. Install the **matching** `sonic_colours.apworld` in
   `C:\ProgramData\Archipelago\custom_worlds\`. Remove old copies. If using
   a source-style `worlds/sonic_colours` installation, do not install both.
3. Use the separate `SNCP8P_movement_gecko_beta.ini` **instead of** the
   prior 4-group Gecko export. Replace its `[Gecko]` and `[Gecko_Enabled]`
   sections in Dolphin's game INI, preserving unrelated settings. Do not append
   it alongside the old four groups. All four groups of the replacement profile
   should be enabled after verifying the INI in Dolphin's Game Properties.
4. Start Dolphin/Sonic fresh. The client starts **normally** via Archipelago
   Launcher or opening the `.apsonic`. **Do NOT pass**
   `--experimental-direct-hooks`. That former DME guest-injection path is not
   required for this beta; it previously produced an invalid read/crash.
5. Use the matching schema-7 `.apsonic` and room (previous schema-7 seed works
   when the game string/slot-data match). The client should say
   `movement hook present` then `armed native movement test via Dolphin Gecko C2`
   when a stable living Sonic actor exists. Run `/sonicmovement` and
   `/sonicstatus`. `installed_signature_verified` is a **byte-check only**.
6. Try Double Jump first WITHOUT its AP item, ideally in Tropical Resort Act 1
   on a disposable fresh save. If it is genuinely denied, obtain/receive that
   AP item and verify the movement becomes available. Then test Jump Dash,
   Homing Attack, Wall Jump, Ground Pound and Progressive Crouch stages.
7. On ANY Dolphin invalid read, hang, or crash, stop and close the emulator.
   Keep Dolphin's PC, invalid address, and `/sonicstatus` log. Fully restart,
   do not resume an in-session savestate created after experimental corruption.

The client additionally provides `/sonicbinding` for save attribution and
`/sonicwater` for **read-only** underwater flags. The beta intentionally does
not fake success: `native_gate_verified:false` means **no live proof of
successful movement denial yet**. It does NOT mean the signature failed:
see `installed_signature_verified` and `controller` for that.

## Swim / Breath research limit

The seven original Aquarium Park Act 1 MEM1/MEM2 pairs corroborate water
bitfield differences in `player stats+0x10`, jump-status bit changes in
`stats+0x08`, and native drowning state ID 100. The `player+0x94` owned plugin
(VTable `0x8075FEB8`) is legitimate, but the correlated float at
`plugin_address-0x30` is NOT proved to be the native oxygen timer: it may be a
separate object with an effect/animation clock. Attempts to find a reliable
countdown field by snapshot deltas yielded no conclusive owner or reset path.

Do not write that float or patch `NativeHooks.swim()` based on it. Required
further captures: `land -> water-enter -> land`, and
`warning five -> bubble pickup -> warning reset`, same scene with minimal
frame advances, plus native PP-debugger watchpoints on the true water timer
writer/reset function. Desired implementation once proved:
`Swim` unlocks underwater jumps; `Breath` separately restores vanilla oxygen;
without `Breath` the native visible drowning warning starts at ~10 seconds
remaining/after submerging (per user design), and each real bubble resets to
that 10-second allowance instead of vanilla. No instant death, no infinite
native flag forcing, and no fake AP status.

## Offline tests performed

- Original PAL main.dol SHA256 and hook opcode exact match.
- Generated movement Gecko code size 3144 bytes <= 3256-byte budget.
- Simulated 11 C2 installations plus authentic native text hash reconstruction.
- Movement C2 control-data readback and signature verification after writes.
- PowerPC ANDI instruction encodes source mask r10 and scratch output r9.
- Seven original underwater RAM captures match the read-only water probe.

These tests do NOT emulate all game physics or Dolphin's actual JIT execution.
