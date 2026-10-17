# Sonic Colours (Wii) Archipelago

Supports PAL **SNCP8P Rev0**, Archipelago 0.6.7+ and Dolphin.

- [Features, options and verification limits](docs/sonic_colours.md)
- [Installation, patching, connection and troubleshooting](docs/setup.md)
- [Default player YAML](examples/SonicColours.yaml)

Generate a seed, open the player's `.apsoniccolours` in Archipelago and select
Dolphin and your original ISO. The local patcher creates a separate native AP
ISO. Manual AP Gecko codes and Riivolution are not required. Keep generated
images and original resources local; distribute only the APWorld/player patches.

Build: `python worlds/sonic_colours/build_apworld.py` produces
`build/apworlds/sonic_colours.apworld`. Tests:
`python -m pytest worlds/sonic_colours/test`.

The two maintained guides are under `docs/`. The release builder generates the
stock WebHost's required game-info filename from the overview; use the built
APWorld for WebHost deployment. Private native test assets remain in ignored
`notes/` and are excluded from releases, alongside tests, caches and reports.
