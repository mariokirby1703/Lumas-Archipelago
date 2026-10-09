# Sonic Colours (Wii) PAL — Archipelago 0.3.0

PAL `SNCP8P`, revision 0; slot schema 3. This build contains native gameplay
readers and guarded writers, immediate journaled checks, and two Gecko hooks.
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
music, or visible counter changes in Dolphin. White Boost scripted grants,
White's discovery event, native DeathLink/Swim and level shuffling remain gaps.

- [Installation, New Game and YAML migration](docs/setup_en.md)
- [Current implementation and exact validation limits](docs/gameplay_overhaul.md)
- [Default YAML](examples/SonicColours.yaml)
- [Migrated Luma YAML](examples/Luma_Migrated.yaml)

Build: `.venv/Scripts/python.exe worlds/sonic_colours/build_apworld.py`.
Original Wii binaries, private notes and RAM dumps are excluded from the APWorld.
