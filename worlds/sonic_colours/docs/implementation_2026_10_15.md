# Sheet V2 and native reliability implementation ? 2026-10-15

Starting source: `86742827203c82edbac7559c45047542d4c2980d`, current branch
`Sonic-Colours-Wii-AP`, fetched against origin before editing. Implementation
commit: `cd64ce55d31edeba0c9ecdc42af35ecd37112c69`; the accompanying follow-up
also preloads oxygen policy through authenticated results/death/respawn scenes.
The attached `CODEX_MASTER_PROMPT.md` was read in full before implementation.

This is **not a claim of complete production/live verification**. The black Act
model issue remains unresolved. No Dolphin process was running at the read-only
live check (`DME: notRunning`, zero candidates). Historical user-confirmed live
results below were preserved, not repeated against this new executable.

## Feature and evidence matrix

| Feature | Code / automated evidence | Current Dolphin evidence / remaining work |
| --- | --- | --- |
| Wisp pool switches | PASS: all 16 Boost/Movement/Game Land/Capsule combinations, exact 7/8/10/11 counts; shared native/logic ownership projection | New normal-item IDs need a fresh seed/live receipt test |
| Random Capsules | PASS: absent without Game Land Checks; Useful normally, Progression with Capsule Sanity; non-story capsule policy has no missing-item lock with Game Land Checks Off | Test both native capsule modes in a fresh seed |
| Sheet V2 | PASS: all 298 real records integrated into `Rules.py`, exact catalog/key validation, individual pickup routes, positive/negative OR/tier tests and rank-result separation | Sheet strategies still need gameplay confirmation; Advanced routes remain disabled |
| Seed fill | PASS: 100 complete, beatable fills for every switch combination (1,600); traversal-order regression; small check-set currency bundling | Logical solvability does not prove every movement route in game |
| Progressive Breathing | IMPLEMENTED: two original-byte-checked native hooks; all seven supported durations execute in PPC tests, bubbles, level changes, owner replacement, foreign profile rejection and host write allowlist | UNVERIFIED: underwater entry, bubbles, pause, surfacing/re-entry, respawn and every tier in Dolphin; old Gecko-only path retains host fallback |
| Capsule capture | IMPLEMENTED: committed-open path before despawning callbacks; coherent queue, per-save attribution, durable dedup, cross-stage and foreign-save tests | UNVERIFIED: rapid White/Cyan pickups and Aquarium checkpoint 1770 in this build; overflow is reported, not reconstructed |
| Game Land Emerald UI | IMPLEMENTED: resolve allocated panes directly, no lazy-wrapper-cache prerequisite; first-presentation fixture and redraw ordering pass | UNVERIFIED: initially missing Yellow outline may also involve native visibility/animation |
| Black unlocked Act icons | **UNRESOLVED**: existing adjacency/path fix retained; no speculative model replacement or host pointer edit | Still needs a safe native model replacement/refresh and visual proof |
| DeathLink | PASS in protocol/PPC tests: native request/ACK, dedup, no echo, unsafe-state deferral, pause/owner checks; Off rejects incoming effects | Historical two-client enemy/pit and remote death/respawn success retained. Drowning, Game Land/Assist, transformations/Super, save transitions and reconnect/expiration matrix remain UNVERIFIED |
| Dead Weight | PASS in PPC/host tests: 30 gameplay seconds, input/state gates, native ACK, pause, duplicates, successive receipts, restart uncertainty, death overlap and owner changes | Historical real-server Jump lock/recovery retained. Rails, stunts, all Wisps, stage transitions, respawn and scripted softlock-safety matrix remain UNVERIFIED |
| Rings / 1-Up / Boost Refills / Ring Loss | PASS: guarded capture fixtures, repeated receipts, context changes, readback, clamping, restart and uncertainty tests | Historical Game Land normal-Sonic delivery while Assist active retained. Repeat across Acts, prologue, respawn and both White ownership states in this build |
| Score Reset | PASS: native stage-score addressing, durable receipt/readback and trap classification tests | Historical actual-server 33,400 ? 0 and red HUD confirmed; no new live run claimed |
| Check delivery / reconnect | PASS: irreversible events checkpoint before slow UI work; durable earned queue retransmits through authenticated AP identity; real local WebSocket capture/ACK tests | Actual Dolphin item/HUD latency still unmeasured; do not infer a new millisecond figure from host tests |
| Music popup | PASS: native event/PPC tests, seeded audio-leaf rewrites against original CSB, loop filtering, scene restart, common 5+5 second fade and publish ACK model | Actual audible normal/FX identity, scene matrix and resource lifetime/long-session behavior remain UNVERIFIED |
| Native ISO workflow | PASS: deterministic container and full DOL revision handshake; actual WIT source/output DATA verification and combined HUD/music CPK build | New ISO not booted/live-tested during this task; `boot_verified` and `live_verified` remain false |

`versions.json.live_validation.deathlink`, `.dead_weight` and `.music_popup`
remain **false**. No test result sets them to true. Developer-only YAML can
explicitly opt into the incomplete native feature matrix:

```yaml
Sonic Colours (Wii):
  native_feature_tests: true
  death_link: true
  dead_weight_trap_weight: low
```

This hidden option defaults Off and is excluded from standard templates/web
options. Use a disposable test seed/save. The normal production guard still
rejects unverified DeathLink/Dead Weight generation without that opt-in.

## Pools, logic and compatibility

| Boost Lock | Ability Locks | Wisp items |
| --- | --- | --- |
| Off | Off | 7 single normal colour unlocks |
| On | Off | those 7 + White Boost Wisp = 8 |
| Off | On | Cyan/Orange/Blue/Purple + two each Drill/Hover/Spikes = 10 |
| On | On | previous 10 + White Boost Wisp = 11 |

Normal Yellow Drill, Green Hover and Pink Spikes append IDs **847000055,
847000056, 847000057**. All previous item/location IDs and retired holes stay
unchanged. Normal unlocks immediately include Turbo, Ring Dash and Spin Dash;
progressive variants require the second copy. Old progressive receipts in an
Ability Locks Off seed also grant complete abilities. This normalization does
not fabricate ownership of any unreceived colour. White is available without
an item when Boost Lock is Off; ordinary enemy/capsule gains and AP refill
permissions remain separate.

Terminal Velocity requires the seven colours plus White only when locked.
Its sequence remains Act 1 ? Final Boss ? Act 2; Act 2 is the final-boss goal
completion. Native world access uses the same option-aware ownership helper.

The supplied JSON is executable source, not an unused resource: 66 Clears,
180 individual Red Rings, 31 1-Up routes and 21 Eggman Hearts. All 297 Normal
records and the one special record are recognized. There are 47 documented
Movement records and 251 undocumented ones; undocumented Movement notes do
not invent extra requirements. Explicit `None` is free, not an unknown fallback.
`advanced_routes` remain separate in the preserved source and never unlock a
standard route. Wisp-availability annotations are not item requirements.

Rank observations are additional access requirements, never a substitute for
an actual native grade/result. The native grade continues to decide which rank
check was earned; score/time metadata never writes a rank or awards a check.
The unresolved Asteroid Coaster Act 5 S-rank strategy conservatively requires
all colour abilities and applicable movement tiers, excluding Assist when its
item is absent from the pool. This is not a guarantee of player score/skill.

Review queue decisions: the ambiguous Normal expressions for `stg320:ring:4`,
`stg410`, `stg430`, `stg430:ring:5` require the union of their stated Normal
requirements. This intentionally excludes the ambiguous shortcuts. `All*` at
`stg790` resolves through the YAML-selected seven/eight base unlocks. Raw notes,
source cells/URLs and Advanced routes remain available for later refinement.

CollectionState now has explicit indirect dependencies for sequential Acts and
boss access. Currency keeps its exact AP value but is bundled more tightly
in small check sets. The early shuffled world must have an initially doable
first Act; it can actually expand the opening check pool. No Wisp is precollected
or forced at a fixed location. The restrictive fill still prevents self-locks.

New slots use `options_revision: 5` / `logic_policy: sheet_v2`. Old schema-7
slots retain their old policy marker, old item IDs and journal digest; normalization
adds the disabled native-test toggle without changing their identity. A new seed
is necessary to receive the corrected pools and V2 placement logic. Regenerating
only an ISO does not rewrite an existing server's placements.

For newly generated slots, journal identity also includes a hash of the AP server
endpoint. Different room ports hosting the same generated seed no longer inherit
one another's receipts. Same-endpoint reconnects preserve the journal. This cannot
identify a server reset that reuses both the same endpoint and seed; legacy slot
journal keys remain unchanged for compatibility.

Known, fingerprinted older player containers can rebuild with current native
code. Existing ISO files are preserved; a component-specific output name is used.
Repatch with the new APWorld to obtain the native oxygen and capsule fixes. The
original PAL ISO must remain the source, never a previously modified image.

## Native boundaries and remaining limits

Oxygen: update `801F0BAC` / original `C03D0020`, reset `801F11E8` / original
`D0030020`. The native elapsed clock uses a floor of `30 - allowed_seconds`,
with 30.05 for immediate drowning at level zero. Supported durations are
0/5/10/20/40/60 seconds; retired Breath retains vanilla 30. Reset applies in
its native callback, not after a host sample. Level changes retain elapsed time.
GPRs, CR and live FPRs are restored; native warning/death behavior stays native.
Only authenticated profile policy is published from the host, and unknown scenes
fail open. First ownership acquisition/scene transitions still require live tests.

Capsules: `800D4CF0` / original `C3FC0104`, after native rejection checks and
before committed spawning callbacks. Entries include the actual save container
and selected byte as well as mission/object/instance/colour/actor identity. An
entry is invalidated before reuse; sequence/head publication follows payload.
The 32-entry queue survives actor removal but is bounded. More than 32 unconsumed
openings can overflow; diagnostics report the count. It is not an offline pickup
archive and does not guess missing checks from despawn alone.

Exactly-once receipts preserve the existing safe limit: a verified ACK/readback
confirms delivery; a proven prewrite rejection defers; an ambiguous partial native
publication becomes `uncertain` and never automatically replays. An external host
cannot make a multi-write native transaction atomic. Inspect `/sonicstatus` and
use `/sonicrecover skip INDEX` only after resolving an uncertain delivery. AP
Rings, life/boost refills and Ring Loss continue targeting normal Sonic in Game
Land even while Assist is active, matching the user's confirmed preference.

Music files/layout were not edited. Preserved `music_display_names.json` SHA256:
`6aafc7d6b6f894dad16389001d8ce8cb78db731c6c902fede0ba96f5debdbaef`.
The user's anchor 800, fonts, colours, positions, 5-second hold + 5-second fade,
formatting and five item notification slots remain intact. Audio graph tests
prove leaf rewrites, not which dynamic branch was audible during a live frame.

Black icon research: `80268FD0..80269030` selects a status-dependent native model
at construction, then stores its reference at actor + `154 + slot*9C`. Updating
status/adjacency/path vertices does not replace that model. A safe replacement
must account for scene-owned resource registration/refcounts; it was not guessed.
The Emerald change likewise does not force visibility or award ownership.

## Verification artifacts

Private local artifacts are under `build/sonic_handoff_2026_10_15/`:
`focus_release.xml`, `committed.xml`, `baseline_full.xml`, `seed_matrix_release.json`,
`iso_build.log`, and `integration.iso.sonic.json`. The baseline was separately
extracted from the exact starting commit; its run reported 17,824 passed,
118 failed, 137 skipped (private capture discovery differed during initial
collection). Compare shared failure IDs, not pass counts as an identical fixture
matrix. See [the automated summary](verification_2026_10_15.json) for the committed-source run
and [the 1,600-seed audit](seed_matrix_2026_10_15.json) for exact generator input hashes.

The dedicated current feature selection passed **415 tests**, including actual
local WebSocket protocol/ACK integration; the native/compatibility follow-up selection also passed (see its count in the summary).
The committed-source complete suite reported **18,127 passed / 25 failed**.
One new checkpoint-test stub lacked the durable journal data introduced by the
transport change; the follow-up fixes that fixture and re-runs its ACK/ordering
test successfully. The other 24 failure IDs also failed in the baseline. Their
messages are listed in the automated summary; several assert retired defaults,
goals/schema or older instruction layouts. They have not all been proven harmless
or resolved. The complete suite is **not green**, and is not native live proof.

A reproducible developer seed audit is provided:

```text
.venv/Scripts/python.exe worlds/sonic_colours/tools/verify_seed_matrix.py --seeds 100 --output build/seed_matrix.json
```

The release APWorld is built with `build_apworld.py`. It includes new runtime
modules, normal-item IDs, the real logic dataset and required local patch tools.
It excludes private originals, CPK/DOL/ISO files, captures and generated HUD assets.

Private integration ISO build: native component
`0c27cd93a3589a8dad2a1a3debfb85495e4aa75ef61f0474352496bdac1976d3`,
output ISO SHA256 `e9f857b2a08647d198cc8a6ea8fef97ef3c6d63eab3b63ad4638e066b21cb725`.
WIT verified source and output DATA partitions and the source ISO hash stayed
unchanged. This isolated test image uses `SonicTest20261015`, not the user's
existing server seed. No copyrighted source or generated image is committed.
