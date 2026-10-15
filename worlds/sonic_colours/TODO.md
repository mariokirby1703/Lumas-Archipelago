# Outstanding verification and implementation

Current implementation/evidence: [2026-10-15 report](docs/implementation_2026_10_15.md).
Historical observations below remain useful; a code fix is not a live pass.

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
- **Latency:** earned native checks are checkpointed earlier and durable queues
  retry after reconnect without a Dolphin poll. Measure actual AP-to-HUD latency
  again; historical controlled observation was about 2.7 seconds.
- **Music:** preserve the user's current layout, fonts, anchor 800, names and
  timing. Complete audible donor/normal-FX, scene/result/Game Land, fades,
  reconnect and long-session resource-lifetime tests. No visual changes made.
- **Release gate:** DeathLink/Dead Weight/music live-validation flags remain
  false. Hidden `native_feature_tests` is an explicit disposable-seed test opt-in,
  not production verification. Full-suite historical fixture failures remain
  listed in the verification report.
