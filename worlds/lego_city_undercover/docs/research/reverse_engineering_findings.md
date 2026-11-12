# Reverse engineering findings

Research performed on 2026-11-11, against the user's supplied Windows files.
Original files remain at notes/gamefiles and were only read.
See file_inventory.md for complete file hashes and collectible_mapping.md for category counts.

Implemented and exercised: full-file inventory, PE headers/strings, ten CC4 archive indices,
CRC-verified name association, bounded ZIPX decoding, targeted script/table extraction and candidate reports.
The scanner data includes internal district names and lock types/ability names.
Its 1,059 rows include 658 Clue entries and must not be advertised as 1,059 collectible checks.
The 92 side-mission definitions overlap scanner objectives and must not be added as independent checks blindly.
The tiny districts.txt has one district definition; it is not a comprehensive city boundary table.

The game's own scripts expose a promising route through CityObjective_IsComplete, UnlockAbility and Job values.
This favors investigation of an in-process, game-thread action bridge over unverified external writes.
No final bridge architecture is proven and no DLL has been installed.

[Mouse Support](https://github.com/twisted89/Lego-City-Undercover-Mouse-Support) was inspected as an external reference.
Its native source tree was not successfully retrieved; proxy exports, hook library and compatibility are unverified.
The [LCU QuickBMS source](https://github.com/linterniGamer/Tt-Games-quickbms-scripts/blob/main/files/ttgames_LCU.bms)
provided the format reference. No third-party executable or extracted game code was executed.

There is no APWorld release, dedicated AP client, received-item effect, automatic check transmission,
ability gating or in-game notification implementation yet. Parser tests do not establish gameplay functionality.
