# Sonic Colours (Wii) ? PAL Archipelago integration

Development version 0.2.0, slot schema 2. **Not yet playable end to end.**

The latest rework removes automatic Wisp precollection and the Slot-1-only rule.
The eight Wisps are shuffled progression items. New Game/bootstrap/save binding,
independent read polling and capsule instance validation now have explicit models.
Native scene/identity and gameplay permission hooks still need PAL evidence.

The live pointer failure has been repaired. Tropical Resort Acts 1..3 clear bits
have been observed through save and reload; this limited read proof does not enable
save binding, check transmission or effects. See the [live repair report](docs/live_client_blockers.md).

- [Setup and migration](docs/setup_en.md)
- [Current implementation report](docs/development.md)
- [Native evidence and smallest live probe](docs/ram_research.md)
- [Example YAML](examples/SonicColours.yaml)

Build: `.venv/Scripts/python.exe worlds/sonic_colours/build_apworld.py`.
The archive excludes `notes`, tools, tests, original Wii binaries and RAM dumps.
