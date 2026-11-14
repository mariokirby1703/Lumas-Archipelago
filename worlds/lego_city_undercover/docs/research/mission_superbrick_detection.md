# Mission Super Brick native detection

2026-11-13: controlled Mine_Cavern P_pup2 collection. Before/after snapshots
showed 80,472 -> 81,472 building bricks, no new city pickup bits and no change
to object instance flags +0x158. The generic pickup handler at RVA 0x9a68d0
sets word [pickup+0x160] bit 0x2 at instruction 0x9a690e. The collected object
subsequently read +0x160 = 0x7. This is distinct from the city save-bit branch.

The reader now exposes this flag, the native scene name and source identity.
Unique scene/name matches for native types 12/29 and standalone source types
80/106 can reconcile mission Super Brick checks, including collected objects
still loaded when the client reconnects. Disappearance alone never counts.
This does not prove persistence after leaving/reloading the mission.

The missing source section was not malformed. Record 190 (Industrial_Steadfast)
contains a parent extension: tail byte 8 = 1, tail byte 9 = string byte length,
then parent name, three local floats and one trailing byte. The old parser failed
to consume that extension and subsequently rejected the entire section. The
parser now consumes and bounds-checks it; mine_cavern's 266 records are accepted.
The same fix also admits a previously rejected scrapyard section. Unknown
layouts remain rejected rather than heuristically resynchronizing.

P_pup2 is source record 101 in section 20544 at resource coordinates
[6.412521, 5.717169, -12.723776]. The regenerated catalogue assigns location
1553847122. A live read-only detector validation selected that exact location,
with native_collected=true. No server checks or game writes were issued.

Existing seeds did not include this previously omitted source. Their clients
can display the detected fund but cannot submit an unknown location ID. New
seeds using the updated catalogue include it under super_bricks. Already present
standalone sources can use the new detection without regeneration.
