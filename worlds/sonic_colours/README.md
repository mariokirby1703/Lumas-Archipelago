# Sonic Colours (Wii) PAL — Archipelago 0.4.0

PAL `SNCP8P`, revision 0; slot schema 4. This build contains native gameplay
readers and guarded writers, immediate journaled checks, and three Gecko codes.
It is ready for targeted testing, but a complete native playthrough has not
been verified.

World Access and all eight Wisp items always use AP ownership. Seven coloured
Chaos Emerald items always appear as progression and control Super Sonic.
Five goals, random post-intro Starting Act, automatic Red Ring packing and
680 optional individual Wisp Capsule checks are supported by the generator.
Music shuffling redirects the native normal-Act cue table before stage loading.

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
goal. Terminal Velocity requires all eight Wisps; a TV starting-stage exception
applies only to that stage. [Validation and remaining limits](docs/oct10_validation.md).

The remaining-requirements patch corrects the Yellow Drill/White gate mix-up,
removes blanket early World/Wisp fill and synthetic Clear events, and renames
the AP counters to Red Ring, 5 Red Rings and 10 Red Rings without changing IDs.
[Exact changes, evidence and unfinished requirements](docs/oct10_remaining_fixes.md).
