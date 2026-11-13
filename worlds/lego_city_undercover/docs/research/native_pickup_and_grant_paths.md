# Native pickup identity and character commit paths

## Pickup writer: exact code path

Collection function RVA 0x9a68d0 receives a pickup in r8 (copied to rdi).
At 0x9a691d it reads its effective type byte +0x193, indexing the native type
table through global 0x1c9df10 (two pointer dereferences), stride 128, flags +0x18.
For flag 0x4000000, and only in the observed city bank branch, it tests:

- game statistics +0x335d;
- local pickup index byte +0x163 != 0xff;
- pickup instance flags word +0x158 must not contain 0x200.

Object +0x48 gives component; component +0x20 gives owner; owner +0xb18 gives
tile descriptor. Tile bytes +0x208/+0x209 are x/y; multiplier global 0x1165910
is 38 in this build. At 0x9a699c the collector ORs a byte in global pickup manager
+0x120 + y*38+x with 1<<local_index. Hence bit=(y*38+x)*8+local_index for index 0..7.
This is native writer evidence, not a nearest-distance hypothesis. It does not
cover story red bricks, shields, character discovery banks, or every pickup type.
The new reader reports a derived city binding separately from an actual pickup
event; the native statistics-mode branch and transitions still need game tests.

## Loaded instance validation

Local pickup component uses vtable 0xd89948, list +0xe0, links object +0x28.
Observed object vtable 0xc2ed28; inline name +0x58, position +0x78.
Read-only scene-registry exploration found 29 components. Their lists contained
137 objects, of which 20 met the city persistence identity guards. All 20 matched
the predicted bit, source name and static city resource sequence. Artifacts:
live_all_native_pickup_bindings.json and live_loaded_pickup_components.json.
Registry entries with unsupported/stale/non-level owners were skipped; this is
not evidence all scene registry slots are loaded city levels.

## Static source registration hypothesis and exceptions

Filtering GIZ source records to types 80/106 (the two city Super Brick types) and
using their ordered local rank explains all 471 source rows. Raw GIZ record
indices cannot be substituted for that rank. This explains 0822 raw index 20
being rank 4 / bit 6756, and 0902 raw index 3 being rank 2 / bit 682.
The native assignment of that rank during resource loading is not fully traced;
unobserved rows remain static candidates. There are 468 distinct candidate bit
IDs and 3 collisions, caused by separate 0919 and 0919_tech resource sequences.
Those 6 source rows must remain ambiguous until combined registration is traced.

build_city_pickup_bindings.py preserves all candidates and exports only the 20
live instance matches to bridge/city_pickup_bindings.json. Existing isolated
collection labels merge with these into 25 monitor labels. The experimental AP
catalogue now has runtime pickup bindings for those 20, and Client.py can send
their newly observed bit transitions. It must not auto-bind all static candidates.

## Character discovery and ownership are separate functions

First v13 collection test: user_monitor_v13_pickup_test.json records bit 1577
at 06:27:51, byte 197 mask 2, byte 0 -> 2. The previously live-bound source is
P_pup1 in WI_Farmlands_0705 (tile 7,5; local index 1). This confirms a real
collection transition for that identity. Actor position is saved. The per-event
native_object_observations list is empty, so this test does not demonstrate
capturing that instance during the pickup itself or sending an AP network check.

RVA 0x88a2b0 takes bank rcx/model edx, sets the found bit in the bank and can set
additional banks +0x480/+0x500 depending on model class metadata flags. It then
dispatches a virtual callback through global 0x17ebd38 +vtable slot 0x1b0.
RVA 0x88a290 stores owned byte [bank+0x80+model]=1, then dispatches slot 0x1a8.
Thus editing bank bytes alone omits native callbacks and is not a complete grant.

CommitCollectables action 0x105ff0 calls 0x23d40 on character controller for the
selected commit branch. 0x23d40 iterates pending class IDs at +0x16a together with
per-entry bytes +0x18a, calls 0x88a2b0 and 0x88a290, resolves linked class models,
then commits extra IDs at +0x1a0/count +0x1ac. It clears pending arrays and repairs
selection state. This routine affects multiple pending grants, not one AP receipt.
The later disk save and exact callback effects still need tracing before calling
this a durable AP grant. No native calls or item-grant writes were made.

AwardCharacter's action 0x1059c0 additionally checks gameplay mode, resolves model
name, marks discovery through 0x88a2b0 and prepares UI/native action effects.
UnlockCharacterDebug's previously found descriptor points to a success stub;
that stub must not be mistaken for an implemented grant function.

Live resolution of model-manager virtual slots gives ownership callback 0x25870
and discovery callback 0x258c0. The ownership callback checks a model property
through 0x834bd0 and can unlock ability index 0x30 (SuperStrength) through 0x90e00.
The discovery callback inspects model data +0x50/+0x20e, clears a supplemental
bank +0x480 bit on one branch and otherwise dispatches 0x26af0. These are concrete
side effects missing from a direct bank-byte assignment. Neither callback alone
has been established as a durable disk-save operation. Resolved RVAs are saved in
live_inventory_callback_rvas.json; no callback was invoked by the investigation.
