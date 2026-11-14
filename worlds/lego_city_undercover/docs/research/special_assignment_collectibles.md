# Special Assignment collectible research

## 2026-11-13: native current-mission mask connected

The descriptors for TL/TR/BL/BR all point to pickup callback RVA 0x6a110.
Its UI-arrival callback RVA 0x6d980 compares descriptor IDs 0x18c, 0x18e,
0x190, 0x192 and ORs 1, 2, 4, 8 into byte +0x50 of the manager referenced
by RVA 0x11754b0. A read-only live sample after the user's upper-right pickup
returned mask 2 and native scene Mine_Tunnel. Source resource scene names map
that scene to mission mine; the existing seed contains mission:mine:TR,
location 1313869694. A read-only client dry run matched exactly that quarter.
No validation tool sent server checks or wrote game memory.

The client now reconciles this current-mission mask, logs individual quarters,
and sends only active quarter/whole locations. Whole requires all four bits.
This supports the existing generated quarter IDs without a new seed. Other
quarters use the statically decoded mapping, pending separate live tests.
Past-mission persistent shield storage remains unresolved; this byte alone
does not backfill every previous mission after leaving it.

The sections below describe the earlier investigation and its limitations.

User requirement: mutually exclusive shield-check option `whole` (one per complete
four-part shield) or `quarters` (one per distinct quarter). Both modes require
independent native part detection. Never add a whole-shield check on top of four
quarter checks. `bridge/mission_checks.py` implements and tests this grouping policy
only; it is not wired into an APWorld or a native level reader yet.

## Native distinctions established statically

The initialized pickup descriptors identify four distinct labels/type bytes:

| Native label | Low-byte pickup type | Descriptor file offset |
|---|---|---|
| Police Shield TL | 119 | 0xff7120 |
| Police Shield TR | 120 | 0xff71a0 |
| Police Shield BL | 121 | 0xff7220 |
| Police Shield BR | 101 | 0xff72a0 |

Each descriptor has its label pointer at +0 and type byte at +0x20. GIZ pickup
names alone do not establish whether a particular resource record is the active
quarter for a puzzle: instantiated or spare pickups can exist. Do not infer quarter
count from the number of matching source records.

The rooftop resource contains Robber_SnakesSquealer, NPC_ConradPeters,
Van_Broadcaster, Police_Bastion and a red pickup. The associated Job script
standalones/sf_rooftop/sf_rooftop.sf unlocks Parkour on first story entry and changes
Act1_Mission to 8 when leaving. This matters for later AP reward suppression and
contained mission replay; native entry itself can grant an ability.

## Important false lead excluded

Achievements_ShieldsDone's name getter is 0x3bee0; its descriptor at file offset
0xc1ebf8 calls 0x85a0. That method ORs a caller-supplied bit into an achievement
manager byte +0x12f and counts five bits before setting an achievement flag.
This is not evidence for a four-quarter per-mission save mask. Do not expose it as
the shield collectible reader.

The executable includes TRUE_HERO_IN_LEVEL, ALL_SHIELD_PIECES_IN_LEVEL,
STATUS_SHIELDPIECE and statsTrueHeroBar strings. The `truehero` resource parser
branch at 0x7e9039 sets a definition flag 0x80000000; this is not a collected-Hero
save flag. Runtime progress, threshold and persistent completion remain unresolved.

## Planned runtime comparisons

The city-side entry baseline is live_first_assignment_entry_before.json. Obtain
another baseline once loaded into the assignment, then isolate a shield quarter,
character/vehicle token, Hero threshold and level completion. Compare transient
level state with saved progress and replay persistence. The current monitor sees
global character/vehicle discoveries but has no verified reader for shield quarters,
Hero or level completion. Do not require a complete first playthrough's collectibles:
missing classes/abilities can make freeplay-only sources inaccessible.

No game writes or scripted actions were invoked. Static findings are from the
hash-gated local executable and resources, not from importing the Manual world.

## User monitor log: antenna reward

The supplied 10-record log is preserved as user_monitor_sa1_log.json, with a review
report beside it under ignored notes/analysis. It includes manual Level betreten,
Schildteil TL and Schildteil BL observations. TL was an explicit user annotation
but has no verified native shield state; the prior tentative third-robber source
must not be treated as proven by that annotation.

At 18:40:48, all three Clue flags SF_ROOF_BL01/02/03 changed false -> true in the
same monitor sample: hashes 3250954001/2/3, bit indices 734/735/736 respectively.
At 18:41:03 the user marked shield BL after reporting all three antennas built.
This supports association with the bottom-left antenna group. Because all three
flags changed together, they do not yet prove one persistent per-antenna counter;
the source could batch-commit the group at completion. Never turn these three
Clue flags into three additional AP checks. A native BL pickup/ownership reader
is still required for robust replay and whole-shield grouping.

The log also confirms campaign cursor 6 -> 7 and the Parkour unlock. Native city
tile lookup is unresolved inside the assignment. The preceding Cherry Tree Hills
heading is therefore historical, not a verified current area for the standalone.
