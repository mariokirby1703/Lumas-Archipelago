# Persistent mission completion, Hero and shield quarters

The native descriptor table pointer is RVA 0x1c7d430, count 0x1c7d438,
descriptor stride 0x350. The first 64 bytes contain the resource path; the next
64 contain the native level name. The progress table pointer at 0x1c7d510 has
20-byte entries with the same native index.

Completion is byte +0xa mask 0x10, written by the level-end branch at
0x9cb649 and 0x9cb739. The low nibble of that byte persists shield quarters.
Bytes +4/+5 are Hero flags, not level completion; the Hero award branch at
0x9cbcd8..0x9cbe81 checks definition flag 0x80000000 and writes those flags.
They must not be confused with mission completion: rooftops and prison were
complete while both Hero flags remained zero.

The before-Mine record at index 4 was 0000000000000000004000000000000000000000.
After completion it read 00000000010100000040360000000000eedea844. This agrees
with the user's Hero and quarter pickups and the story script advancing
Act1_Mission 9 -> 10 only after Standalones.Mine.Finished > 0.
The live read also identified completed rooftops and prison entries.

The reader binds by exact native Standalones/<resource> path rather than guessed
level order or the player's current scene. It skips city/secondary areas and
checks table identity and record consistency again before accepting a sample.
The connected seed dry run selected mine: Complete, ID 1122314298, while the
player had already returned to Lego_City. No native writes or server messages
were issued by the validation.

Completion, Hero and quarter/whole checks now reconcile from this persistent
table, so they can be recovered after leaving a mission or reconnecting.
Blackwell's Mansion has two native entries sharing one existing catalogue
resource. Its grouped completion requires both; collectible flags are not merged
across those two missions. Separating their locations is future catalogue work.
