# Sonic Colours (Wii) ? PAL Archipelago integration

Development version 0.2.0, slot schema 2. **Not yet playable end to end.**

The client now sends physical Red Ring and capsule checks from native gameplay
state, including the mandatory unsaved intro. A durable AP journal retains
pickups through death, exit, disconnect and server-ACK retry. Red Ring groups
use the five physical identities collected across attempts, not save masks.

Native results-screen Clear/Rank checks now report before intro save selection.
World Access unlocks its first Act and refreshes the current waypoint cache;
status presentation is debounced independently from pickup polling.

Native Rings, 1-Up and Ring Loss delivery, selected-save World/starting-act access,
AP Game Land gates, seven colour permission fields and the Super unlock bit have
real compare/write/readback paths. Item receipts now settle after separate
0.5/2-second counter observations, rather than immediate readback. Save resume uses witnessed native slot,
profile and intro result records; no invented guest UUID or padding is written.

**The full integration remains incomplete:** White Boost and tutorial/capsule
initialization interception, native DeathLink/Swim, level shuffle and booted music
validation are outstanding. The normal AP Wisp mode is not fully enforced.
Use [the in-game test setup](docs/immediate_checks.md) to exercise the implemented
client. Original-capture write overlays and a local WebSocket server test do not
constitute live Dolphin gameplay validation.

- [Setup and migration](docs/setup_en.md)
- [Current implementation report](docs/development.md)
- [Native changes, evidence, music installation and exact remaining gaps](docs/native_implementation.md)
- [Native evidence and smallest live probe](docs/ram_research.md)
- [Example YAML](examples/SonicColours.yaml)

Build: `.venv/Scripts/python.exe worlds/sonic_colours/build_apworld.py`.
The archive excludes `notes`, tools, tests, original Wii binaries and RAM dumps.
