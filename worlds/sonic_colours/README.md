## V10 experimental update (2026-10-12)

This source includes a **New Game Boost provider pointer fix** and a **native-request guarded movement rearm experiment**. Without White Boost Wisp and without an AP refill, enemy gains must be clamped to zero by the next client poll. The V10 replacement Gecko INI is **required** for the new movement experiment, and existing V8/V9 Gecko must not run alongside it. **Dolphin playback/live gate success is not yet verified.** See `docs/movement_boost_v10.md` for installation and test limitations. Swim and Breath native restrictions remain unimplemented.

> **CURRENT EXPERIMENT: early movement-request gate V4, 2026-10-12.**
> The preceding Fallback V3 was disproven by real Dolphin tests: native denial
> telemetry incremented but Crouch and Ground Pound left Sonic stuck.
> V4 intercepts earlier at 0x8003388C and replaces disallowed requested state
> arguments with the existing state, BEFORE native state-change callbacks.
> Dolphin playback of V4 remains UNVERIFIED. Use ONLY the replacement Movement
> Request Gate V4 Gecko profile, never alongside the old V2/V3 Gecko groups.
> [DOL disassembly, testing and caveats](docs/movement_request_gate_oct12.md).
> Swim and Breath are separate items but native water gates are still absent.

> **Experimental schema 7 movement research build (October 11, 2026).**
> The new opt-in Movement Unlocks option creates Wall Jump, Homing Attack,
> Mid-Air Boost (Jump Dash), Double Jump, Ground Pound, two Progressive
> Crouch levels, **Swim and Breath as separate items**. Native state locks
> are ONLY available in the **unverified no-Gecko direct-PPC experiment**;
> standard Gecko does not implement them. Underwater Swim/Breath locks,
> Hover's scripted ghost spawn and the cached unowned world castle are
> **not fixed yet**. See [movement_schema7_experimental.md](docs/movement_schema7_experimental.md).
> New schema-7 seeds are required; normal AP 0.6.7+ client compatibility remains.

# Sonic Colours (Wii) PAL — Archipelago 0.6.0

PAL `SNCP8P`, revision 0; slot schema 6. This build contains native gameplay
readers and guarded writers, immediate journaled checks, and four Gecko codes.
It is ready for targeted testing, but a complete native playthrough has not
been verified.

World Access and all eight Wisp items always use AP ownership. Seven coloured
Chaos Emerald items always appear as progression and control Super Sonic.
Five goals, a fixed mandatory introduction, automatic Red Ring packing and
680 optional individual Wisp Capsule checks are supported by the generator.
Music On shuffles all 78 looping BGM cues in one global pool; the nine finite tracks stay vanilla
through the verified resident CSB bank, retaining destination control graphs.
No external music files are required. See [global music and Wisp correction](docs/global_music_and_wisps.md)
for the implementation and remaining audible validation.
The live White-capsule test exposed disabled collision bodies after refresh;
[the native reactivation fix](docs/white_collision_fix.md) requires the updated
capsule code and still needs post-fix contact/pickup validation.

The capsule hook now initializes the original native pickup collision objects,
including repair of capsules previously refreshed only visually. The progression
hook intercepts vanilla World/Wisp/Super grants and records native discovery and
Game Land clear transitions. Existing opened capsules and clear/rank records
are preserved.

Offline tests exercise original RAM captures, guarded real-address writes,
PowerPC hook execution, restrictive AP fill and genuine local server protocol
acknowledgements. These do not establish usable capsules, audible shuffled
music, or visible counter changes in Dolphin. White pickup/script and ordinary
Boost gates are implemented but need live validation with the updated Gecko code.
White's discovery event, native DeathLink/Swim and level shuffling remain gaps.

- [Installation, New Game and YAML migration](docs/setup_en.md)
- [Current implementation and exact validation limits](docs/gameplay_overhaul.md)
- [Default YAML](examples/SonicColours.yaml)
- [Migrated Luma YAML](examples/Luma_Migrated.yaml)

Build: `.venv/Scripts/python.exe worlds/sonic_colours/build_apworld.py`.
Original Wii binaries, private notes and RAM dumps are excluded from the APWorld.

The October 10 update accepts exact older AP capsule thunks, adds native
Game Land speed and optional Boost-use gates, randomized Rings and Half Boost
Refill, and requires the final boss plus the subsequent escape for the default
goal. Terminal Velocity automatically opens with all eight Wisps; its separate Access
item and starting-stage exception are retired. [Validation and remaining limits](docs/oct10_validation.md).

The remaining-requirements patch corrects the Yellow Drill/White gate mix-up,
removes blanket early World/Wisp fill and synthetic Clear events, and renames
the AP counters to Red Ring, 5 Red Rings and 10 Red Rings without changing IDs.
[Exact changes, evidence and unfinished requirements](docs/oct10_remaining_fixes.md).

Schema 5 adds opt-in Egg Medal Sanity (21 immediate native pickup checks),
White capsule ghost/interaction projection and Half Boost Refill without White
ownership. Update all four Gecko codes and generate a new seed. Story Speed
Sanity and Movement Unlocks are not exposed: a safe native story locomotion cap
and ability-specific transitions have not been established. The new medal and
White hooks are code-derived and tested offline; complete gameplay validation
is still required. See [new abilities validation](docs/new_abilities_validation.md).

## v0.6.0 / schema 6 testing patch (unverified in Dolphin)

- Public **Eggman Heart Sanity** (21 Game Land locations; the native class is still EggmanMedal).
- **Music Randomization** is On/Off (default On). The client now recognizes the
  exact PAL `sound/bgm.strm.csb` 87-cue bank resident in MEM2 and mutates only
  globally assigned audio leaves while retaining destination control graphs,
  including all ten Wisp cues, without an extra CPK. A loaded song
  may not switch until a new cue is started. No audible Dolphin validation yet.
- **Starting Act / Level Randomization removed**. Tropical Resort vanilla intro
  is fixed. **World Progression** is Sequential (default) or Open Acts.
- `--experimental-direct-hooks` offers DME-only hook installation with all Gecko
  codes disabled. **WARNING:** potential crashes, unstable code arena and Dolphin
  JIT cache non-coherency; never use your only save. This is NOT verified as a
  stable Gecko replacement. See [experimental guide](docs/runtime_experiments.md).

Regenerate both APWorld and seed. Previous schema-5 seeds do not work in this
schema-6 client; do not delete or repurpose your old journals.

## Experimental Movement Gecko BETA (2026-10-11)

For Dolphin-managed PPC movement testing, see [Movement Gecko BETA](docs/movement_gecko_beta.md). Its `data/SNCP8P_movement_gecko_beta.ini` REPLACES the original Gecko codes (do not combine). The verified source/Gecko installer tests are offline-only. **Swim and Breath remain separate AP items but native underwater/oxygen gates are not implemented yet.** The older `--experimental-direct-hooks` mode is not recommended after an invalid-read crash.

## Movement Fallback TEST (2026-10-12)

The old C2 deny branch skipped native state entry and could lock Sonic in Ball Form (`-1 -> 8`). The new **experimental native fallback** preserves the entire original state transition and exposes guest-only deny counters. Gecko profile **MUST replace**, not supplement, the older movement profile. See [dump analysis and installation](docs/movement_fallback_dump_oct12.md). Swim/Breath remain without native gates.


**Movement Request Gate V5 (diagnostic only):** see [V5 lifecycle telemetry](docs/movement_request_gate_v5.md). The actual V4 request hook is retained but augmented with cumulative guest counters for all handler entries and Sonic-owned requests, to debug controller changes across stage reloads. This is not a certified movement fix.
