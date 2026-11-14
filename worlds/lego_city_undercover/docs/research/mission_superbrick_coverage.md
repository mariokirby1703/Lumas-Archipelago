# Mission Super Brick coverage

All parsed standalone Super Brick sources use the shared native collected-flag reader.

41 source locations; no rejected pickup sections remain. Zero means no source of types 80/106 was found, not proof that no other reward exists.

| Mission resource | Super Brick sources |
|---|---:|
| bank | 3 |
| blackwells_mansion | 0 |
| construction_site | 7 |
| fire_station | 0 |
| icecream_parlour | 0 |
| mine | 8 |
| moon_base | 0 |
| museum | 7 |
| police_station | 1 |
| prison | 8 |
| rooftops | 0 |
| scrapyard | 3 |
| secretbase | 0 |
| space_centre | 0 |
| temple | 4 |

Version 13 uses a three-byte type field; version 14 uses four bytes. Both layouts, parent attachments, full section consumption, scene aliases and native type agreement are checked.

All listed sources pass detection/binding round-trip tests. Live collection was tested only for Mine_Cavern P_pup2. Persistent replay after leaving a mission is not implemented; current loaded collected flags are reconciled.

A client update handles already-existing locations. Newly recovered source records require regeneration with the updated APWorld; the same YAML and game save may be reused.
