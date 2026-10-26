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
APWorld for WebHost deployment. Optional private native test assets live outside
the world in `build/sonic_colours_reference/` at the repository root. They are
excluded from releases, alongside tests, caches and reports.

## Spreadsheet logic (completed V3)

The APWorld now uses `data/logic_from_sheet_v3.json` and `logic.py`
for all 298 explicit NL/ML location routes. NL applies when Ability Locks
(`movement_unlocks`) are off; ML applies when enabled. An alternative route
(`or`, `/`) is an OR branch; `+` combines requirements. Progressive tiers
use the actual Archipelago item counts. Normal Wisp variants work when Ability
Locks are off. Speed Lv1 is the starting Game Land speed, so the first
Progressive Game Land Speed item unlocks Lv2.

A/S rank checks require the stage's clear route and **every Wisp in its
`rank_wisps` list**, plus any S-specific movement requirements when Ability
Locks are on. B/C rely on the ordinary clear route. Score and time achievements
are still determined by the actual game, not by item possession alone.

The APWorld uses documented standard routes for seed generation. Sequence-break
(`advanced_normal`/`advanced_movement`) routes remain encoded in the JSON for
trackers but **are not** considered by the AP server's seed-fill logic.

Corrections included: all four Aquarium Park Act 1 Red Ring 4 movement routes;
Game Land 7-3 Clear and Eggman Heart require Random Capsules in both documented
ML alternatives. The Random Capsules item is classified as progression when
Game Land and Ability Locks are both on, to avoid casual filler placement.

`logic_policy=sheet_v2` remains in slot data for compatibility with the
existing PAL client validation protocol; `logic_engine_version=3` identifies
the updated APWorld rule engine. No item/location IDs changed.
