# Outstanding verification and implementation

Current implementation/evidence: [current feature and verification summary](docs/sonic_colours.md#logic-and-verification-limits).
Historical observations below remain useful; a code fix is not a live pass.

- **Underwater Drill turbo:** live Aquarium Park boss had Water Drill state 76
  with the ground/manual turbo permission at zero. Its independent held-action
  predicate at 801F6D2C was unpatched. The native build now masks that result
  with the same authenticated permission word as ground Drill, before the
  boost/effect/internal-state calls. Repatch and verify manual turbo at Drill
  levels 1/2 underwater; preserve normal drilling and scripted acceleration.

- **Rail action gates:** native grind side-change and jump decision helpers
  now check Rail Switch / Rail Jump before issuing an action. The jump helper
  covers both button and alternate input paths; held side actions additionally
  require Switch. Denial returns no action and keeps the current rail, with no
  forced Fall/reattachment or input-buffer mutation. Repatch and verify stages
  0/1/2 of Progressive Rail with rapid presses and held directions in Dolphin,
  including automatic rail-end/gimmick exits. Those scripted exits stay native.

- **Scripted movement recovery:** live Asteroid Coaster Act 1 had active Drift
  (38) with the movement gate armed and only Homing permitted (mask 4).
  Native Drift, Stomp and air-jump update callbacks now independently recheck
  permissions and exit through ordinary Run/Fall requests and cleanup. Queued
  deaths/scripted exits are preserved. Verify the corrected ISO at this Drift
  and after Aquarium Park Act 6 water currents/fans; the latter is not yet
  captured live. Air-jump uses Swim underwater and Double Jump above water.

- **Homing/Double Jump fallback:** the native air-action selector now treats a
  locked Homing selection as no selected action, preserving native Double Jump
  eligibility and the existing state permission gate. PPC and original-DOL
  validation pass. Repatch the ISO and verify a targeted enemy/object with
  Double Jump owned, Homing absent, including a second attempted air jump,
  underwater, and Dead Weight. Owned Homing must still work normally.

- **Unresolved:** AP-unlocked Area Map Acts can still use a black locked model.
  Adjacency/path rendering works. Safely replace/refresh the status-selected
  scene-owned model without leaking references or changing clear/locked styling.
- **Progressive Breathing:** native update/reset hooks are implemented, with PPC
  tests for 0/5/10/20/30/40/60 seconds. Verify immediate water entry, bubbles,
  surfacing, loading/results/respawn, pause and level changes in Dolphin. The old
  Gecko-only host fallback still has polling latency. Historical level-1 air was
  about 28 seconds instead of five; do not mark that observation fixed live yet.
- **Capsule Sanity:** committed-opening capture now precedes spawning callbacks,
  survives actor removal, identifies the selected save and checkpoints checks
  before slow UI work. Test rapid White/Cyan collections, TR Acts 1/2/3 and
  Aquarium Park Act 1 checkpoint 1770 without stopping before each capsule.
  Controlled earlier pickups passed, ordinary fast pickups were unreliable.
  Native backlog is 32 entries; an overflow is explicitly reported.
- **Game Land Emeralds:** direct allocated-pane resolution replaces the lazy
  wrapper-cache prerequisite. Verify initially empty Yellow visibility without a
  Record/menu round trip. Colours alone do not prove native visibility/animation.
- **DeathLink:** retain successful historical two-client enemy/pit/incoming
  tests. Complete drowning, Game Land, Assist, transformed/Super Sonic deferral,
  reconnect, save/scene switches, expiration, duplicates and no-loop recovery.
- **Dead Weight:** retain the confirmed native 30-gameplay-second Jump lock and
  release. Complete rails, held jump, stunts, Wisps, transitions, respawn,
  reconnect, repeated traps, DeathLink overlap and scripted softlock safety.
- **Fillers/traps:** repeat Rings/1-Up/Half/Full Boost/Ring Loss/Score Reset across
  Acts, prologue, deaths and Game Land in this build. Normal-Sonic targeting while
  Assist is active is intentional and user-confirmed. Score Reset was actually
  delivered through the server at 33,400 ? 0 with a red HUD entry; this is not an
  unimplemented trap. Earlier guarded 600 ? 0 also passed visibly.
- **White Boost Lock:** verify white capsules and enemy gains before ownership;
  AP Boost Refills must remain usable. Earlier user observation was inconclusive.
- **Boss-dropped Wisp capsules:** lock capsules dropped by Frigate Orcan and
  Skullian during their boss fights when the corresponding Wisp is not unlocked.
  Frigate Orcan's live White/Cyan drops use vtable 8077E080, colour +60 and
  consumed byte +74, rather than ReleaseBoxSmall. A boot-patched pickup guard
  at 802E7E28 now checks the authenticated capsule/progression permissions
  before any reward or consumption. Requires a newly patched ISO. PPC and
  original-DOL checks pass; live locked/unlocked pickup tests are still pending,
  including Skullian. Native ghost mode is now selected at spawn and refreshed
  on permission changes through the original model constructor/reference owner;
  collision, physics and consumed state are preserved. Visual live validation
  remains pending. The live Cyan unlock exposed a container-vs-flags owner
  mismatch; the guard now derives container + 0x24 + index*0x19608, tested
  against the actual save resolver for all four native records. Re-test the
  corrected build live.
  Inspect their spawned capsule actors/pickup paths separately from placed
  capsules; verify that locked drops cannot grant a held Wisp or Boost energy,
  and that drops work normally after the relevant AP unlock.
- **Unowned Wisp HUD residue:** live Aquarium Park boss state 97 had empty
  current/pending slots but Yellow in the previous/display slot. The client
  now clears all unowned inventory/display residue and colour timers while
  preserving Boost. State 97 cleanup requires fresh underwater ownership,
  empty usable slots and zero active time; active transformations still defer.
  A subsequent live read confirmed all three slots/timers were already empty
  but cockpit +1b0 still cached Yellow. The new native cockpit reconciliation
  sends the original removal event on the game thread; authenticated AP Wisp
  permissions protect owned icons and queued owned replacements. Requires a
  repatched ISO. Verify the actual icon disappears live without changing Boost.
- **Latency:** earned native checks are checkpointed earlier and durable queues
  retry after reconnect without a Dolphin poll. Measure actual AP-to-HUD latency
  again; historical controlled observation was about 2.7 seconds.
  Actor-list reads now use two process reads per actor instead of four; pure
  hook assembly/comparison data is cached without caching guest validation.
  Early map projection no longer configures every gameplay hook twice per poll;
  item delivery precedes optional music-bank reconciliation. Live-test both
  sequential Act paths and the six-clears boss path: the reported ten-second
  delay is not yet demonstrated resolved. Also measure client UI responsiveness,
  check-to-server, receipt-to-effect and receipt/music-to-HUD times separately.
- **Music:** preserve the user's current layout, fonts, anchor 800, names and
  timing. Complete audible donor/normal-FX, scene/result/Game Land, fades,
  reconnect and long-session resource-lifetime tests. No visual changes made.
  Finite-song replay now checks the current native channel/cue and invalidates
  stale end latches on successful music starts. Re-test both full songs through
  Wisp entry/exit and a real song end in a newly patched ISO; PPC tests alone
  do not establish audible resume/loop correctness.
- **Release gate:** DeathLink/Dead Weight/music live-validation flags remain
  false. Hidden `native_feature_tests` is an explicit disposable-seed test opt-in,
  not production verification. Full-suite historical fixture failures remain
  recorded in local full-suite test output under build/.

- Live verification pending: native held-colour query rejects unowned Wisps before transformation selection, even with a stale hidden inventory icon. Test rapid Laser activation before/after AP unlock with the updated ISO; unit PPC matrix covers all colours and save indices.

- Live verification pending: Random/multi capsule output filters each coloured flying Wisp before allocation using authenticated AP ownership. Observed Game Land stgC10 with AP mask 1 and flying colours 0/1 before fix. Verify updated ISO emits Yellow Drill only until Cyan Laser is unlocked; all five spawn callsites and seven colours covered by PPC tests.
