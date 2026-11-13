# Disguise-specific interaction fields

User request: identify the object/type and native usage conditions, then investigate
independent AP locks, potentially per district. Player action context alone is not
the detector. Monitor v10 reads loaded GizSwitch/Techno objects, predicts floor
marker variants and reads the native scan-marker registry. It does not implement
AP locks or claim proven underfoot/inside-aura detection.

## Monitor coverage and requested extensions

v9 adds an independent interaction pane and change history. Candidate loss,
unsupported types and read errors clear the current candidate presentation.
Clipboard/JSONL records include identity, position and flags, without generating
AP checks. Session diagnostic snapshots also retain this state. The native slot
is sampled once per second; transient interactions can be missed.

v10 adds tabs for loaded objects, scan markers and history. Full field lists and
marker changes are copied/exported as diagnostic records, never AP checks.
In the current prison scene, 18 GizSwitch objects and one Techno were read live.
This includes ordinary switches, robber doors, a safe, axe fields and detective
objects. Other interaction systems and unrecognized layouts remain unsupported.

Remaining validation: actual rendered visibility, full interaction eligibility,
exact underfoot occupancy and geometric scan-aura occupancy. Registered native
scan markers are an independent signal, not inferred from player context or
merely owning a scanner. UI distinguishes unavailable readers from an empty
registry and does not label the latter as proof of being outside every aura.

### v10 native scene and marker paths

Scene resolution follows RVA 0x506d30: entity interface virtual +0x10 is the
verified 0x487160 getter (ushort at interface +0x18, actor +0x28). Global
0x1c402d8 indexes records at +0x18+id*8; record +0xd8 gives owner. After checking
owner +0xb18, owner +0xbb0 gives level, level +0xa0 gives component container,
whose +0xc0 table is indexed using each global system's +0xf4. This is the
previously missing ownership path, replacing the invalid actor+0x20 guess.
Local GizSwitch vtable is 0xc34ed8, Techno is 0xc36198. Both lists start +0xe0
and link through object +0x28. Verified object vtables: 0xc34578 and 0xc35a98.
Ownership (+0x48), cycle limits and scene/list stability are checked.

The marker decision function at 0x800a0 chooses exact native floor sprite IDs
632..661. Runtime sprite table global 0x1c7ebd8 has 24-byte records, name pointer
+8; count at 0x1c7ebe0. Read-only lookup confirmed all names, including Crowbar
645, Stethoscope 647, Robber_Locked 654, Fireman_Locked 655, Constr_Locked 659.
Primary class registration at 0x17ebe70 uses 16-byte records, IDs
227,228,237,234,233,232,230 for cop/robber/miner/astro/farmer/fire/construction.
`floor_markers.py` preserves native branch precedence and extra EnergyGun/Jetpack
ability requirements. Owned/pending class observations predict a variant; this
is explicitly not a complete reproduction of every availability-query special
case, nor proof the sprite is currently rendered. Unknown inputs stay unknown.
The field's `locked` remains null; `marker.class_lock_candidate` is a prediction.

Manager 0x17ec098 +0x110 is an actual selection candidate: 0x8b9fdf stores the
object, +0x118 stores squared distance and +0x11c stores the decision returned
through manager virtual +0x158 (city implementation 0x7f3f0). Reader exposes the
raw result, pending in-game interpretation, rather than calling it a bool.

Scan registration path 0x854f0 reaches player state through global 0x17ebc90
+0x138, local player pointer at state +0x1770+index*8. Inline accessors +0x440,
+0x288,+0x18,+0x58 and scan collection +0x258 give player +0x990 (vtable 0xc7f028).
0x231f60 selects AudioScan (0), CriminalScan (1), DetectiveMode (2), then hashes
the type and registers it via 0x231da0. Collection +0x38 is a linked list through
+0x10; marker payload +0x20 points to definition, +0x30 contains
position and +0x60 the instance hash. Payload and renderer objects are distinct:
their paired pointers at +0x28 must not be confused when investigating radii.
The live registry is empty at the second crowbar door; nonempty scan cases need
the planned in-game comparison. No exact occupancy or scan-running flag is claimed.

v12 correction from the first nonempty user log: definition +0 is a NuString
header (0x10001), not a type hash. The type name's NuString is at +0x30 with
string pointer +0x38. A bounded read of the already logged definition resolved
DetectiveMode there, with SC_DetScan at the sprite-name pointer +0x18. The old
v10/v11 records saying "Markierung 0x10001" must not be interpreted as unknown
native scan types. v12 derives type_hash from the actual type string and retains
native_type_name; this correction still does not prove geometric occupancy.

First corrected nonempty in-game confirmation: user_monitor_detective_aura_waiting.json
records DetectiveMode / Detektivscan at 03:23:17.607, type hash 3223415943,
instance hash 2256374136, position (3.940110,1.377909,0.781470). User independently
reports standing in a detective aura before scanning. The marker persists while
the generic GizSwitch candidate becomes distant and then clears. Thus the scan
registry supplies a signal independent of the selected furniture/switch object.
Do not change inside=null based on this one observation; leaving/reentry and scan
activity comparisons are still needed.

Exit/reentry follow-up (user_monitor_detective_aura_exit_reentry.json) contains
232 cumulative records versus 225 in the preceding log, but no new
scan_markers_change record. The same DetectiveMode instance remains registered
through 03:25:47 while GizSwitch candidates change/clear. With the user's requested
exit/reentry test as context, registry membership cannot serve as an inside-aura
boolean. The log does not prove a geometric boundary crossing; retain inside=null.
Repeated boundary walking is not sufficient to decode occupancy from this list;
inspect sensor/render activation data separately and compare an active scan next.

Active-scan follow-up user_monitor_detective_scan_completed.json adds 14 records:
LegoItem at 03:28:29.386 -> DetectiveMove (24) at 03:28:30.370 -> LegoItem at
03:28:34.517 -> Default at 03:28:34.954. At 03:28:34.521 the registered
DetectiveMode marker disappears, and #cg_244_DETECTIVE_CUPBOARD_SW has state flags
0x200. Its native selection result changes from 0 to 3 at 03:28:35.612, followed
by a separate GizSwitch action 03:28:35.826–03:28:38.115, after which flags are
0x206. Keep the completed detective sequence and subsequent furniture use
separate: marker removal is not a generic AP check or universal scan-completion
predicate. DetectiveMove is useful supporting active-action evidence, not the
detector for merely standing in an aura. Exact occupancy remains unresolved.

## Names established in the executable

Robber floor-marker variants include:

- Hotspot_Ability_Floor_Robber_Crowbar
- Hotspot_Ability_Floor_Robber_EnergyGun
- Hotspot_Ability_Floor_Robber_Stethoscope
- Hotspot_Ability_Floor_Robber_Locked

Other classes have their own floor/locked variants, including construction drill,
hammer and coffee cup; fireman axe and extinguisher. These are visual resource
identifiers, not automatically interaction class names or permission flags.
The initialized sprite descriptor references are 24-byte rows: Crowbar file offset
0x117a290, Stethoscope 0x117a2c0, Robber_Locked 0x117a368. Direct RIP references
to those individual rows were not found; dynamic table indexing remains unresolved.

stuff/hotspots.txt defines story/race/parkour mission icon categories, not these
disguise-specific gadget markers. Do not treat a story HotSpot.SetActive operation
as a proven generic tool-interaction gate.

## Object systems and local evidence

Prison_MainCells GIZ includes a Techno record with type GringottLock, object
CellDoor_01, instance Lock_01. Its source record has a candidate coordinate triple
at payload +77 of (1.83653,0.99501,3.35843), which is not sufficiently close to
prove identity with the reported field at (6.76393,0.99478,1.42911). Do not label
the player's current field Lock_01 without additional evidence. Builder instances
such as SAFE_HIGH_CMPLX can represent other interactions and need separate mapping.

Native LegoTechnos constructor is RVA 0x9dff50; GizmoTechnoManager constructor
0x88960/nearby name reference 0x8897d; city system constructor 0x889d0 has vtable
0xc35fa8. Read-only lookup found this system through RVA 0x17ec940. Its global +0xe0
list is empty in the observed state, so it is not a working enumeration of loaded
interaction fields. A speculative level-local resolution was rejected; no zero or
invalid pointer dereference was converted into a guessed object identity.

The generic Techno traversal at 0x9e66a0 loops instances through +0x28 and uses
definition pointer +0x180 and position +0x78. The v10 ownership path above resolves
the loaded instances. 0x9e1d60 handles several linking modes and cached object
pointers; it is not established as the class/ability permission predicate.

CanUseGizmo is a native script action with constructor 0xa686c0, registered near
0xa6f017. Its presence is an investigation entry, not proof of a callable public
gate or a safely understood invocation. No function was called in the game.

## Remaining work for detection and locks

### Live second-door identification

Read-only before-opening probe resolved the GizSwitch system at global RVA
0x17ec098 (manager vtable 0xc34ae8). Its +0x110 slot points to an object with
vtable 0xc34578 and inline name at +0x58:
`#cg_433_BNE_STEELDOOR_SW`. The global +0xe0 list is empty; this slot, rather
than that list, supplied a concrete candidate. Full slot selection/retention
semantics remain unverified, so do not yet expose it as a universal active-field
detector. Repeated bounded snapshots confirmed the same object and content.

Object origin (+0x78): (1.474387, 1.993083, 3.414915).
Interaction position (+0x22c): (1.458987, 1.986588, 3.086915).
Player position: (1.474981, 1.981715, 3.113374).
Requirement flags (+0x24c): 0x110100. The 0x80000 explicit crowbar-item bit is
**not** set. Thus the earlier item-specific branch must not be presented as this
door's actual prerequisite. This object has bit 0x100 set: the branch at 0x7fa5b
calls 0x24cf0 with required category 1 (Robber). The earlier category-0 note was
incorrect: edi already holds 1 from 0x7f81a. That routine compares character categories
derived from metadata; it is not an independent AP-tool permission query.
The other set bits and complete decision path still require interpretation.

The source template BNE_STEELDOOR_CMPLX at prison_maincells.giz file offset 31148
has instance name iBNE_STEELDOOR_CMPLX2 and origin
(1.475950, 1.993083, 3.417863), approximately 0.00334 source units from the native
origin. Matching family, scene, origin and interaction proximity make this a
strong source-instance candidate, not a proven persistent identifier. The earlier
door's source candidate BreakAndEnter01 at offset 32641 is separately located near
(6.778485, 0.994773, 1.719435); do not conflate them.

Reproduce the bounded, hash-pinned read with tools/probe_interaction_target.py.
Saved output: notes/analysis/live_interaction_target.json. No interaction was
triggered, no game code called, and no process memory written. A verified AP lock
must add permission to the correct interaction decision path; hiding the marker
or relying solely on possession of the crowbar would not establish that lock.

### Further static trace: crowbar-specific prerequisite

Exact executable string `crowbar` is passed to 0x9d1c50 at RVA 0x516b9;
the preceding call result is stored at global RVA 0x17ecb98 (0x516b2).
References to that global occur at 0x5185f, 0x7fe25, 0x8419e and 0x1b05a4.
This is more specific than the generic player context, but the global's pointed
definition type has not yet been confirmed dynamically.

At 0x7fe18 an interaction candidate in r15 tests dword +0x24c against
0x80000. If set, it requires a non-null crowbar definition, obtains its byte
at +0x138 and passes that identifier to 0x7c5160 with the player item controller
returned by 0x66a420. A null result takes the rejection path 0x7fe96.
At 0x84192 a matching 0x80000 test uses the same definition and lookup, then
passes the resulting item to 0x7c7600 (item activation). This is strong static
evidence for a crowbar requirement bit plus item lookup and activation paths.
It does not prove that the current door's live object has that bit: the
relationship between the candidate in r15 and a loaded GizSwitch instance still
needs verification. Return values are multi-valued; do not assume bool semantics
or patch one conditional as a complete AP lock.

0x1b05a0 is another compact crowbar-item existence query using the same definition
byte, controller getter and item lookup. Separately, the GizSwitch resource loader
at 0x8bb1f0 reads serialized data into +0x24c at 0x8bb2ce (and a version-dependent
older path at 0x8bb365). Identical field offsets alone do not establish identical
object layouts; trace ownership/callers before joining these paths.

The property string canuseon_edclass is used at 0x675b63 during object processing,
with IGNORE_CANUSEON registered at 0xbe67c4. Its relationship to these tool fields
remains unverified. No corresponding stethoscope prerequisite has yet been traced.
All addresses are RVAs for the pinned research executable; no code was executed,
patched or injected. Disassembly is saved under notes/analysis/disassembly.

### Player-confirmed prison layout

The player confirms that the currently observed floor field requires the crowbar
to open a door. Behind that door is a safe requiring the stethoscope. These are
two separate tool interactions, not alternative names for the same field.
This confirms the visible tool requirements only: neither the door nor the safe
has been matched to a loaded native instance or a source resource ID yet. In
particular, do not identify the crowbar door as GringottLock/Lock_01 on this basis.
Future AP gates should preserve separate Crowbar and Stethoscope permissions;
this observation does not establish that the native checks are already located.

The subsequent user-confirmed door opening is captured in
notes/analysis/user_monitor_prison_crowbar_door_log.json. At 02:00:47.565 the
player enters GizSwitch (25), briefly returns to Default, re-enters GizSwitch at
02:00:49.857 and returns to Default at 02:00:55.304. At 02:00:50.296 the attached
definitions change to include #ex_719_Crowbar_item at player position
(6.666322, 0.994773, 1.431293). This corroborates a GizSwitch/crowbar interaction,
but GizSwitch is generic and the attachment change alone is not an explicit
door-completion flag or proof of the hand state. No new collection/completion
event is recorded in this final interaction interval. Earlier records in the
same cumulative log must not be attributed to this door opening.

The next supplied cumulative log, saved as
notes/analysis/user_monitor_prison_stethoscope_safe_log.json, contains exactly two
additional records compared with the door log: GizSwitch (25) at 02:02:18.925 and
Default (46) at 02:02:26.667. This was supplied in response to the requested
stethoscope safe test. There is no additional attachment, collection, or mission
state event. Thus the currently monitored fields do not distinguish the two tool
interactions, and they do not independently confirm safe completion. Absence of
a monitor event is not evidence that the native game has no completion state.

1. Resolve loaded action-object ownership and preserve instance/type identity and
   object-space/world-space transform; proximity alone is insufficient.
2. Trace the exact pre-interaction class, tool and ability checks per interaction.
   Separate required disguise from individual tool and AP area permission.
3. Gate initiation before it consumes an item, changes the world or grants a reward.
   Hiding a floor icon does not prevent the interaction. Alternate controls/co-op
   and already-running interactions need explicit handling.
4. Reapply permission state when the level/instance loads, with immediate AP receipt
   handling through the eventual game-thread bridge. Persistent activity completion
   must remain independent from permission state.

Reproduce name/resource inventory with tools/interaction_field_catalogue.py. All
outputs are research metadata under notes/analysis; game files remain unchanged.
