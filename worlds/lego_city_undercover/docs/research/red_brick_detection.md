# Red Brick source and direct pickup checks

## Source-backed catalogue correction

The catalogue contains 22 city locations and 15 standalone Red Brick locations.
Every regular type-114 source has a matching location and passes a detection
round-trip test. Two prison source objects map to the same native mission flag
and location. Blackwell's Mansion instead has two native assignments and now
uses distinct keys blackwells_mansion_1 / blackwells_mansion_2 for Red Bricks,
resolved from mansion1_/mansion2_ source scenes and the native descriptor name.
Police Station has no source record and its speculative Red Brick location was
removed. This covers the parsed source set; it is not a live validation of every
location or proof that all possible non-pickup reward mechanisms are decoded.

Existing generated seeds retain their original locations. Regeneration with the
updated APWorld is required for the separate mansion checks and city sources
that were previously excluded by the unverified-pickup category.

User-reported Datenscan-Upgrade: Hinweise was captured as native pickup
CHEAT_SCAN_POINT_OF_INTEREST in WI_Forest_0701, position
[-230.474945, 13.912535, 394.537750], native type 7, +0x160 flags 0xf
(generic collected bit 2 set). It uniquely matches raw type 114, source
wi_forest_0701.giz section 1018 record 2. The dry run selected location
1063232270. The active seed did not contain that source key.

Type-114 city pickups are now categorized under red_bricks instead of the
unverified raw pickup pool. They use the shared bounded native object reader,
unique scene/name/type binding and collected flag, not currency or scan activity.
City source checks absent from an existing seed require regeneration. The client
logs the collected pickup even when the seed has no corresponding location.

Story Red Brick pickups use their existing mission:<resource>:Red Brick key
immediately, avoiding an additional raw source check. Persistent mission backfill
uses level progress byte +9 mask 2: the native collection gate at 0x6ad2a tests
that mask, and the completed prison record contains it, agreeing with the user's
earlier Studs x2 discovery. City pickup state after unloading is not established
by that per-mission flag and is not inferred from it.

The native-7/raw-114 binding and shared collected flag are generalized to the
catalogued city/story sources; the Hinweise upgrade is live validated. No game
writes or AP messages were performed by validation tools. Receiving or enabling
the AP reward remains separate from reporting the original Red Brick location.
