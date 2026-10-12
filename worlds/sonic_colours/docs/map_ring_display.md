# Physical Ring display before an Act clear (PAL)

The original 80268A80..80268B48 initializer caches all normal Act masks at
map actor +5FC + Act*14, even when its rank-valid byte (+5EC) is zero. The
8026A264 UI branch nevertheless sends an empty rank to its frame-5 placeholder
and skips the Ring icons.

The first C2 at 8026A43C changed only the detailed records panel. The user's
live test showed that the badges above map nodes still did not appear. A
read-only live comparison verified the installed hook and Act 3's cached mask
3 (Rings 1 and 2), rank-valid 0 and rank -1. The collection data was correct.

The corrected C2 at 802697A8 replaces the native conditional skip for each node
badge: actor node +15C must ordinarily equal 4 (cleared). Already cleared
nodes retain their original path. Other normal-world Act nodes also execute
the original badge creation, positioning and icon-frame code. Boss/Terminal
Velocity exclusions retain their original skip. Missing ranks use the native
frame-5 placeholder; Rings are read from the original cache. No save/rank/
score/availability/clear data changes. Old detail-only hooks remain recognized
for executable verification during client updates, but are no longer exported.

Both exports fit the standard Dolphin codehandler. The movement export uses
a 12-byte lookup table for the same eight restricted requests instead of a
48-byte sparse table. The capsule compact epilogue respects the native ABI:
800D4828 overwrites CR0; 800D4850..4860 restores LR. Only r31/r1 and the
displaced r0 load are consumed in the continuation, so saving already volatile
GPRs/LR/CR0 is unnecessary. Native callees preserve nonvolatile GPRs/CR fields.
Every native capsule ownership/model/collision check and call remains present.
Older exact compact/full capsule and V11 movement payloads remain recognized.

Offline tests execute UI branch cases and movement restrictions, validate the
combined profile against the original PAL executable and check the 3256-byte
codelist budget. Rendering the two collected Tropical Resort Act 3 Rings on an
uncleared Act still requires the user's live Dolphin test with the new profile.
