# Super Brick source catalogue

`python worlds/lego_city_undercover/tools/pickup_catalogue.py` reads extracted GIZ files without modifying game files. It produces ignored research artifacts `notes/analysis/superbrick_catalogue.json`, `city_superbricks.csv`, and `pickup_catalogue_summary.json`.

The supported v14 layout has a 36-byte header, then a uint32 type word, int16 reference, uint32 flags, uint8 name length, NUL-terminated ASCII name, three float coordinates and ten opaque bytes. Every accepted section must parse exactly to its end. Seven sections currently have unsupported versions/extensions and are excluded entirely. No claims are made about the reference or opaque fields.

The executable's initialized type descriptors identify low-byte type 80 as `Gold Plate` and 106 as `SuperBrick4X2` (label pointers at file offsets 0xff6aa0 and 0xff7320, type byte at descriptor +0x20). Upper type bits remain preserved separately. These labels do not alone establish a reward amount.

Current result: 7,933 pickup records; 537 records of those two types, including 471 under city resources. Other records include builder templates, missions and test maps. These counts are not a verified count of unique collectibles or AP locations. Templates and overlapping resources need deduplication against live objects.

`source_key` combines archive-qualified resource path, section offset and local index. It is a reproducible source identity, **not a verified native persistent ID**. Names such as `j_pup` repeat. Coordinates are resource coordinates; world transforms for instanced templates are unresolved. CSV districts come from resource folders, not from the player's current district.

# City district and position research

The native registry pointer is RVA 0x17eca20. Functions 0xca6f0 and 0xcab30 access 23 records with stride 0x28, starting at +0xe0. The fixed district-name table starts at RVA 0xc409e0 with stride 64, including `SF_Docks`, `SF_Residential` and `UNASSIGNED`. Record field +4 currently contains sequential values 22–44; it must not be presented as a name hash or current-player district.

The object initialized at 0xc9e50 is a separate component with +0xd0 initialized to -1; this initialization is not proof that the registry's corresponding field reports the current district. Runtime district detection is still unresolved.

`tools/probe_city_position.py` reads the actual player's transform accessor without invoking engine functions. The observed virtual slot +0xf0 targets RVA 0x49ecf0, which copies the transform at interface +0x1b0; its translation is actor +0x1f0. Latest observed position: (-177.01697, 1.04541, -26.35633, 1). This is an accessor-derived snapshot, not yet a movement-correlated verification. The probe rejects unknown executable hashes and does not infer a district from unlocked areas.

All three `Act_1_CatchRobber_*` flags were true in `live_third_robber_chapter1_complete.json`. Chapter completion itself was reported by the player; no independent chapter-completion bit has been established.

# Persistent pickup payload (2026-11-12)

The `LegoCityPickups::SaveLoad` constructor at RVA 0x6aed0 allocates a 0x658-byte
object and initializes a 0x640-byte payload at +0x18. Its vtable is 0xc2f238:
0x6ca30 returns size 0x640, 0x6d830 copies the runtime payload for serialization,
and 0x6cc20 reads it back into the runtime manager. The runtime manager pointer
is RVA 0x17ec808; its observed vtable is 0xc2f268 and payload starts at +0x120.
No native methods were invoked.

`tools/probe_pickup_save.py` captured 1,600 stable bytes and found an exact match
in the current slot-1 backup at offset 412497. The section is framed by the
uppercase FNV-1 hash of `LegoCityPickups` (0x9437dd86), uint32 length 1600, payload,
then the same hash. `pickup_save_data.extract_section` requires exactly one bounded
match, rather than assuming a fixed save offset. Both existing backups satisfy
this framing. The older backup has an all-zero payload; the newer backup exactly
matches runtime. Original saves remain untouched.

Nonzero bytes are offset 654 = 0x38 and offset 694 = 0x04. Raw little-endian bit
offsets are 5235, 5236, 5237 and 5554. These are **four** set bits, consistent with
the four observed +1,000 pickups, but this count alone does not prove individual
identity. An earlier commentary incorrectly counted five bits and was corrected.
Grouping into 800 uint16 words is only a diagnostic view, not established schema.
In particular, bit 5554 is a plausible candidate for the latest `P_pup2` pickup,
not yet a verified assignment. No pre-pickup capture of this newly found payload
exists for that collection event.

An immutable SHA-named baseline is preserved under notes/analysis. A subsequent
single-pickup comparison can now test which bit changes, followed by a native
autosave comparison. `tests/test_pickup_save_data.py` checks section framing,
truncation, ambiguity, payload length and bit numbering. The full suite has 40
passing tests. Runtime-to-source index mapping remains research work.
