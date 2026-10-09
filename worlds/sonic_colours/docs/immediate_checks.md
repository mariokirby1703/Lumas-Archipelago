# Current live-defect fixes

This build adds native results-screen Clear/Rank checks, first-Act access plus
world-map waypoint cache refresh, pause classification and debounced status
presentation. Item delivery synchronizes bounded live counters/mirrors and waits
for separate 0.5/2-second observations before settling a receipt. The scanner
still targets 20 ms; status debounce never delays pickups or server ACKs.

Start New Game normally while connected; `/sonicnewgame` is optional. Results
checks require the native completed result presentation (UI state 7 and awarded
native grade), not a score-derived estimate or a save. B earns B/C; S earns
S/A/B/C. Already acknowledged checks remain durable across save selection.

For delivery testing use a **fresh seed/journal** and receive Rings, 1-Up and Ring
Loss during living gameplay. Watch `received / queued`, `Native write attempted`,
`Immediate readback verified`, then settlement or `uncertain`. Confirm the HUD at
0.5 and 2 seconds, collect another ordinary ring, take damage and change stages.
Counter settlement is not a claim that visible HUD behavior was live verified.
Old confirmed receipts are retained and never re-applied automatically. Crashed
`prepared`/`verifying` receipts stay uncertain; `/sonicrecover skip INDEX` abandons
one explicitly. Zero-ring traps stay queued while later safe filler can proceed.

The supplied screenshots establish working Red Ring transport on the previous
build; this change preserves it. The two new native captures establish missing
Sweet Mountain bit37, its locked first-waypoint cache, and the pause handler.
Both introductory result captures validate the relocated results reader. Private
archive SHA256 manifest was checked; originals are not modified or packaged.

Dolphin reported `noEmu` during this work. Offline tests include actual original
RAM reads, writable overlays, counter reversion, delayed settlement, all-world
flags, Sweet Mountain cached waypoint state and WebSocket result acknowledgements.
The complete Sonic Colours test suite passed: 500 tests. The WebSocket server is
a local protocol test server; this is not a live Dolphin-to-MultiServer session.
**Pending live validation:** visible route/link redraw and playability in every
world; actual HUD/physics after filler/1-Up/trap and later pickups/injury/transition;
a fresh title-to-intro run without a command. No new Dolphin gameplay is claimed.

The historical report below describes the earlier implementation. Its statements
about immediately consumed receipts and save-only rank checks are superseded above.

# Immediate checks and native gameplay testing

This change implements production reads, writes and AP LocationChecks. It does
not complete every requested feature. Dolphin was probed through DME and reported
`noEmu`; no new in-game write or pickup-to-real-AP-server run was performed.

## Start testing

Build/install `sonic_colours.apworld` and regenerate the seed with this version.
For an initial pickup test use `examples/SonicColours_Native_Test.yaml`. Launch
the registered Sonic Colours client, connect to the AP slot before playing,
select New Game before collecting anything. Detection is automatic; `/sonicnewgame`
is an optional confirmation. exact native factory flags, untouched records and intro Act 1
must match. Existing saves cannot establish a new seed binding.

Collect a Red Ring in intro Act 1. The log should show `Pickup detected`,
`Location queued`, `LocationChecks sent`, then `Location acknowledged` from the
server. The last message requires a server packet; a local send is not an ACK.
Open a capsule and check the corresponding instance location the same way.
Neither requires the result screen, save selection or a NAND save.

Finish both mandatory intro acts, select a free native save slot and let the
first map load. The journal binds the selected native index, profile and exact
intro score/time/rank records to the AP bootstrap epoch. A subsequent client or
Dolphin session must match this witness. Legitimate intro record improvements
require an observed attributed replay/result transition. Identical copies of the
same save are indistinguishable; this is not a native globally unique save ID.
Guest padding and unrelated slots are never modified for attribution.

During stable living gameplay, receive Rings, 1-Up or Ring Loss. Delivery uses
resolved native actor fields, compare/write/readback, and a fsynced receipt intent
before the write. A failed or interrupted prepared receipt is uncertain and is
never automatically replayed. `/sonicrecover skip INDEX` explicitly abandons it.
Native life storage is incremented by one; its HUD presentation needs live confirmation.

## Implemented paths and evidence

| Feature | Implementation | Evidence / remaining validation |
| --- | --- | --- |
| Red Ring singles | Rising physical mask bits at actor-state+91, canonical ring identity, durable immediate checks | Intro and cross-attempt automated tests; live timing and AP test pending |
| Red Ring per-level | Journal ever-mask across attempts; emit when all five identities have been witnessed | Loss/retry/restart tests; historical save masks never imported |
| Capsule sanity | Bounded native actor list, Small Capsule vtable, ORC record/wrapper/descriptor identity, static placement/subtype match, opened byte+110 | Original Act 3 actors and consumed overlays; live intro/Game Land/retention timing pending |
| Native save binding | Same-session mandatory intro -> first map witness, selected slot/profile/result records, restart matching | Full original-capture sequence and mismatched-profile refusal |
| Clear/rank checks | Native selected-save C flags and awarded rank records; attributed journal checks | 13 original capture pairs; earlier live save/reload only TR Acts 1..3 |
| Rings / 1-Up / Ring Loss | Real resolved stat writes, limits, readback, exactly-once receipt confirmation | Original-structure writable overlays; actual Dolphin write/HUD pending |
| World / starting-act access | Masked native World flags and chosen act's bank-A availability | Original bound-save write/readback; map refresh and each starting act pending |
| Game Land | Entry and 21 native availability flags projected from AP Red Ring inventory/gates, without fabricated physical pickups | Original save overlay; native routine/UI races need live validation |
| Emerald checks | Seven group checks require all three real native Game Land clears, independent of clear-check option | Automated grouping; live seven rewards pending |
| AP Super permission | Native bit7 only when all seven AP Emerald items are owned; vanilla untouched when option off | Original save overlay; Options satellite/toggle, transformation/drain/infinite Boost pending |
| Colour Wisp delivery | Seven native save bits and live stage/actor masks in native colour order | Original bound actor readback; full native availability remains incomplete |
| AP transport | Real CommonClient sends, durable retry independent of item history/Dolphin, server-only ACK, reconnect identity isolation | Real localhost WebSocket test, intentionally lost first ACK and retry |
| Music | Existing owned-CPK Lua BGM rewrite/readback | Archive verified; rebuilt disc and audio not tested |

The 706 stable capsule candidates retain their original IDs. 680 mapped primary
layer `00` placements are enabled (448 story, 232 Game Land); eight alternative
layer placements and eighteen unmapped missions are excluded. Eligibility is
static: primary layer, registered native object factory, matched subtype and ORC
placement. Traversal logic remains provisional and uses the conservative Wisp
requirements; individual reachability has not been live verified. The native
PAL subtype table is raw `0..7` -> White, Drill, Laser, Cube, Hover, Frenzy,
Rocket, Spikes, correcting the earlier hypothesis labels.

The poll target is 20 ms during gameplay, with bounded linked-list traversal.
The opened byte is retained until the native opening animation/deferred actor
removal, rather than being a one-frame pulse. **There is no injected retained
guest event queue and no proven minimum retention duration**; live performance
and rapid destruction must be measured. A client started after a pickup baselines
existing state and does not invent an event that it did not observe.

## Exact outstanding native operations

* White Boost's normal availability query and independent Super infinite Boost.
* Forced tutorial Cyan grant interception and capsule initialization/visibility
  refresh when a Wisp is received after an actor was already initialized. Save
  bits and current permission masks alone do not fully enforce this mode.
* Cache-coherent native kill invocation for DeathLink; setting lives to zero
  would not be a native death and is not used.
* Reversible Swim Everywhere state with expiry/death/transition/goal restoration.
* Intro-safe real loaded-stage redirection and all level-shuffle YAML modes.
* Real first-map selection of a nondefault starting act (access flag is written,
  automatic menu focus is not implemented).
* Booted music patch, native gate/UI refresh behaviour and save persistence of
  new permission writes. These require live gameplay rather than additional mocks.

DeathLink, Swim, discovery checks and level randomization still reject unsupported
YAML instead of silently claiming operation. Other requested YAML is generated,
but full AP Wisp enforcement and all-goal end-to-end playthroughs are not verified.
The default shuffled Wisp mode is therefore not a complete playable release.

Private original DOL/CPK/RAM files remain outside Git and the APWorld package.

Validation: the complete Sonic suite passed 489 tests before the added ZIP-import
regression; that regression and the two packaging tests subsequently passed.
The effective test suite contains 490 cases, including 13 private original
RAM capture pairs and a real local WebSocket roundtrip with a lost ACK.

## Server identity repair

The client now tracks the actual `RoomInfo.seed_name` independently of the unset
CommonClient `seed_name`, requires it before accepting Connected slot data, and
authenticates the team/slot/server-seed tuple for transport. An idle queue never
reports a transport identity failure. Diagnostics separate gameplay, pickup,
journal, transport and item-write status. The WebSocket regression starts with
`ctx.seed_name=None` and processes RoomInfo/Connect/Connected through CommonClient.
Dolphin again reported `noEmu`; GUI/live ring delivery acceptance remains pending.

Failed journal fsync now holds transmission and retries local persistence even
when AP is offline or a per-level mask has no completed check yet. Automatic
intro detection also seeds the native binding witness on its first observed
fresh poll, rather than depending on a second poll or a manual command.
