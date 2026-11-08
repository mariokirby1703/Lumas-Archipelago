# PAL / NTSC-U disc audit

The supplied local extracts in `notes/PAL` and `notes/NTSC-U` were compared on
2026-11-08. No disc assets are included in the APWorld or audit output.

## Identity and coverage

| | PAL | NTSC-U |
|---|---|---|
| Retail title | Marbles! Balance Challenge | Marble Saga: Kororinpa |
| Disc ID | RK6P18 | RK6E18 |
| Disc revision byte | 0 | 0 |
| Balance Board levels | 100 | 30 |
| Files in DATA/files, excluding .svn | 1214 | 1216 |
| DOL SHA-256 | 81e6714fbbb74376c7bc3785af8d94c4eba08fef0e1e983e4c5a3906407af2aa | b022bc29140b8744bb55a0033274da1ded14cd14cd37865ec1a4860fb001afc4 |

All shared game files were hashed: 1036 identical, 178 changed. The two US-only
files are `.brsar.tmp` / `.brsar.2.tmp` leftovers, not additional game content.
The UPDATE partition and extraction `.svn` metadata are outside the gameplay audit.
The disc's internal header titles are MARBLE SAGA (PAL) and KORORINPA2 (US);
the user-facing US title is Marble Saga: Kororinpa.

All A01-A12 campaign/bonus stage files, including E/H variants, are byte-identical.
The audit decoder successfully reads all 693 AxxSxxx stage files per disc using
the container's zlib and 1-KiB-window LZSS codecs. It records object counts and
collectible model IDs rather than exporting the original stage text.

The existing campaign structure is consistent with the disc data: W1-W6 each
have 11 stages per difficulty; W7 has 10. Model 96 appears in Normal stages
1-10 (70 Green Gems); model 97 appears in Hard stages 1-10 and the Hard bonus
worlds (100 Anthony checks). Model 95 occurs in Easy/Normal W1-W6 stages 1-10
and Hard W1-W6 stages 1-10 (the existing Hard junk-pickup check path).
Normal bonus model-95 stages match the existing capsule list exactly:
WA 1/3/6, WB 1/3/5/6, WC 1/3/5/6.

Both discs contain A15S001-A15S100. Their presence does not prove that all 100
are playable. The US save-record routine reserves 0x1428 bytes (30 * 0xAC)
for the Balance Board array; PAL reserves 0x4330 (100 * 0xAC). Generation must
use 30 US checks even though the unused assets remain on disc. All 100 A15
files differ between the extracts.

## Address derivation

There is no universal PAL-to-US offset. The save getter is at PAL 0x80075524
and US 0x80075200. It computes:

```
PAL:  0x8049D928 + 0xBC + selected_slot * 0x166B8
US:   0x80498728 + 0xBC + selected_slot * 0x137A8
```

For Save Slot 3 (index 2), the bases are 0x804CA754 / 0x804BF734. The stride
difference is 0x2F10: 70 * 0xAC plus 8 bytes of alignment. Accordingly:

| Address family | PAL-to-US delta |
|---|---|
| Early BSS, mode/save-slot selectors | -0x5200 |
| Slot-3 campaign and bonus records, before the Board array | -0xB020 |
| Slot-3 inventory after the Board array | -0xDF28 |
| Later BSS, temporary pickups and hub globals | -0xDF30 |

The marble accessor independently verifies the inventory displacement: it reads
save_base + 0x14C1A on PAL (instruction at 0x80070350), versus save_base + 0x11D12
on US (0x8007002C). The campaign/bonus record selector uses the same 0xAC stage,
0x764 world, and 0x33BC difficulty strides in both DOLs. Normal and mirror trophy
records are separated by 0x50 in bonus stages too.

The audit JSON records the instruction words at the save getter, Board selector,
and marble accessor sites so these derivations are reproducible without Capstone.
The other live globals were matched through corresponding PowerPC instruction
sequences and their containing BSS structures. Heap/MEM2 addresses are deliberately
not extrapolated from these static offsets.

## Implemented changes

- `game_region: pal` (default) or `ntsc_u`, serialized into slot data and restored
  by Universal Tracker. Network game name, item IDs and location IDs stay shared.
- Region-specific static addresses, location records, inventory, vehicles,
  collectible writes and AP counter overlays, including former direct PAL paths.
- Exactly 30 US Board checks; all 100 PAL checks remain available.
- Disc ID must match the generated region before any game synchronization.
  Existing slots without region fields remain PAL; unknown IDs are rejected.
- US goal detection uses the mapped stage-clear flag, including tutorial and Board
  checks, instead of probing PAL MEM2 goal candidates.
- Save Slot 3 guards RAM writes as well as location sending. Previously item and
  inventory synchronization ran before the save-slot guard.
- Bonus mirror trophy addresses are now included, fixing missed mirror trophy
  checks and synchronization for both regions.

## Validation and remaining live checks

The automated world tests cover PAL/US generation, Board counts, reachability,
item pool validity, exact address examples, serialization isolation, disc mismatch,
US clear-flag reads, bonus mirror trophies and the save-slot write guard.

This is a **disc-derived NTSC-U implementation ready for Dolphin testing**, not a
claim of a completed live playthrough. In Dolphin, verify each difficulty, a bonus
world, Board 1/30, a tutorial, goal completion, pickups, inventory persistence and
save/reload on Slot 3. Verify the counter overlay restores correctly when moving
from world map to level select and that no checks/writes occur on Slots 1/2.

PAL's MEM2 goal probes, countdown, saved-junk mirror and heap noclip address cannot
be relocated safely from disc files alone. US uses the static clear flag and live
save inventory; the unverified saved-junk mirror is omitted. US trap chance is
normalized to zero and its experimental trap handlers are disabled until runtime
addresses and timing are verified. PAL trap behavior remains available.

Reproduce the file audit (from the repository root):

```
.venv/Scripts/python.exe tools/marbles_balance_challenge/disc_audit.py --output tools/marbles_balance_challenge/disc_audit.json
```
