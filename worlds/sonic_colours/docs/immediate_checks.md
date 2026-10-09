# Immediate checks and native gameplay testing

This change implements production reads, writes and AP LocationChecks. It does
not complete every requested feature. Dolphin was probed through DME and reported
`noEmu`; no new in-game write or pickup-to-real-AP-server run was performed.

## Start testing

Build/install `sonic_colours.apworld` and regenerate the seed with this version.
For an initial pickup test use `examples/SonicColours_Native_Test.yaml`. Launch
the registered Sonic Colours client, connect to the AP slot before playing,
select New Game and issue `/sonicnewgame` before collecting anything. The command
records intent; exact native factory flags, untouched records and intro Act 1
must also match. Existing saves cannot establish a new seed binding.

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
