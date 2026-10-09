# Sonic Colours — Wii PAL research integration

**Status: implementation in progress; not a playable Archipelago release.**

This world generates and fills research seeds and includes an external Dolphin
client with real, guarded read/write primitives. No native gameplay write or
automatic location detection has passed live PAL validation. The client refuses
to arm a save or send checks until those hooks are implemented and verified.

See [setup](docs/setup_en.md), [development status](docs/development.md),
[RAM evidence](docs/ram_research.md), and the [example YAML](examples/SonicColours.yaml).

The `notes/` directory is development input supplied by the user. It is excluded
from APWorld packages, especially the ELF containing original Wii sections.

Build from the repository root:

```powershell
.venv/Scripts/python.exe worlds/sonic_colours/build_apworld.py
```
