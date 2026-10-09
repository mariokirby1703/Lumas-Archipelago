Current implementation: [Immediate checks and native gameplay testing](immediate_checks.md).
The report below predates native pickup transmission and the selected production writers.

# Development report ? rework 0.2.0

**Release status: incomplete; no real PAL writes or native check transmissions
have been verified.** Offline behavior and live acceptance are separate below.

The [2026-10-09 native implementation report](native_implementation.md)
supersedes the scene/stats/physical-ring/rank and music status below. It documents
original-capture validation, enabled rank/music YAML modes, the actual owned-data
CPK patch workflow, and the remaining unimplemented native operations.

The subsequent [live repair report](live_client_blockers.md) supersedes the
earlier no-emulation result below: actual PAL data reads now resolve the corrected
inline flags structure. Intro bits 150/151 and regular Act 3 bit 152 survived
save and title-menu reload. Only that documented subset is promoted to persisted reads; native
scene, New Game, stable save identity, AP attribution and writes remain blocked.

## Changes from dd23ef600c3046cfa5b4e6670a68aefcf18d7e9e

The new `START_HERE_CODEX.md` and full rework document supersede the older master
spec. `notes/offline_re` contains byte-identical copies of the old README and four
CSV catalogs, not new RAM evidence. The updated audit reads all supplied files.

- Automatic starting Wisps: 8 ? 0; shuffled AP Wisp items: 0 ? 8. Vanilla mode has
  no AP Wisp items. Unknown clears use an explicitly provisional route model;
  unknown Red Rings conservatively need all Wisps. This does not assert exact
  native clear requirements. Override entries can be known/provisional/unknown.
- Public game key `Sonic Colours (Wii)`, slot schema 2 and package version 0.2.0.
  Old seeds/files need regeneration. Existing IDs remain stable, leaving gaps for
  removed D-rank checks and the removed extra item. No separate Super Sonic option,
  item or goal remains. All seven AP Emeralds determine AP Super Sonic permission;
  native projection remains incomplete.
- No hardcoded visible Slot 1 restriction. The new state machine models New Game,
  forced Acts 1/2, vanilla save selection, any-slot binding, resume, identity switch
  and rollback. `/sonicnewgame` confirms intent but requires native corroboration.
  Proven intro checks are journaled by epoch and reconciled before sending. Fake
  adapter tests demonstrate this flow; native New Game/identity fields are absent.
- Native snapshot no longer unconditionally raises. It verifies revision, resolves
  the actual candidate pointer chain and reads the 66 C bits with bounded access.
  It reports candidate clears/provenance. These are deliberately not promoted to
  persisted authoritative checks or a save ID without live evidence.
- Read attribution, inventory readiness, native permissions and stats delivery are
  independent. Deferred writes do not prevent separately verified reads. Unbound
  checks stay local; normal checks retry until server acknowledgement.
- Game Land Emerald reward logic requires completion events for all three acts,
  even if their network clear checks are off. Native reward predicates also require
  the reward plus all three actual clear observations.
- Capsule sanity option, canonical instance catalog, stable reserved IDs,
  validation overlay and permission-aware opening predicate added. No native
  opener is fabricated. 456 story +232 Game Land candidates; 18 unmatched excluded.
  Zero validated instances means non-off modes fail with a specific message.
- DeathLink protocol callbacks/tag configuration and native polling are wired,
  retaining the native-kill capability gate. Unsupported option generation stays
  rejected until the real native event/kill adapter exists.
- Typed native evidence registry records code-derived/dump-correlated/live-read/
  live-write grades and unresolved fields; no capability is promoted automatically.

## Per-feature status

| Feature | Status | Remaining native proof |
|---|---|---|
| World/options/pool/fill | implemented_offline_only | Provisional routes need user logic and native gating |
| BE memory + guarded writes | implemented_offline_only | Actual safe scene/address/identity writer |
| Candidate save-chain/C reads | implemented_offline_only | Running PAL pointer lifetime and persisted C semantics |
| New Game/bootstrap/resume | implemented_offline_only | Native New Game indicator, freshness and stable save ID |
| Red Ring/rank checks | incomplete | Persisted flags, saved rank, 44-stage eligibility |
| World/Wisp permissions | incomplete | Query hook and scripted Cyan tutorial denial |
| Game Land/AP counters | implemented_offline_only | Native gate query/counter projection |
| Emerald/Super Sonic | implemented_offline_only | Native ownership query and boost exceptions |
| Capsule catalog/filtering | implemented_offline_only | Native instance opening/subtype/accessibility proof |
| Rings/1-Up/Ring Loss | implemented_offline_only | Stable stats parent pointer and safe UI-consistent write |
| DeathLink protocol | implemented_offline_only | Death/respawn states and real kill routine |
| Swim trap | incomplete | Safe reversible state routine and exit behavior |
| Level/music shuffle | incomplete | Asset compatibility, CPK patcher or native redirect/playback hook |

There are no `implemented_and_live_verified` gameplay features yet. Existing
capability flags remain false because the new files contain no new live evidence.
Read polling is no longer gated by those write flags; only trusted attribution
and specific effect delivery are deferred.

## Validation

See `validation.txt` for exact commands/results. Tests cover 100 default seeds
with shuffled Wisps present in reachable spheres, 600 additional fill runs, and
precise refusals for unsupported modes. They also exercise the forced prologue,
any-slot binding, same-seed resume, switched/old saves, rollback, independent
reads while writes are blocked, four rank thresholds, Emerald prerequisites,
canonical capsule identity and memory/journal/protocol failure cases.

The user confirmed Dolphin is open **without a running game**. DME returned
`DolphinStatus.noEmu`; no live reads, writes or check sends were performed.
`tools/probe_pal.py` provides a small read-only JSON probe for a later session.

| Default optional settings | Story | Game Land | Emerald | Red Rings | Total |
|---|---:|---:|---:|---:|---:|
| Singles | 45 | 21 | 7 | 180 | 253 |
| Per-level | 45 | 21 | 7 | 36 | 109 |
| Red Rings off | 45 | 21 | 7 | 0 | 73 |
| All optional checks off | 45 | 0 | 0 | 0 | 45 |

Ranks reserve 176 candidate IDs, with native eligibility still unresolved. No
capsule locations are activated before validation. Stage/music planners remain
offline helpers; no in-game shuffle, CPK patch or arbitrary starting-act redirect
is claimed implemented. Normal startup still forces Acts 1/2.

## Next native observations and risks

1. Run the read-only probe at title/New Game, forced Acts 1/2 results and first save
   selection. Confirm manager global 0x808F3628, chain and index lifetime; identify
   native menu/scene transitions and a stable save identifier before binding.
2. Observe C bit 150 (mask 0x00400000 at resolved flags+0x20) around Act 1 clear and
   after actual save/reload; repeat for Act 2 bit 151. Do not write these flags yet.
3. Trace the live stats parent and the Cyan tutorial permission query. The old
   fixed heap addresses and load instructions do not establish writable targets.

Guest writes cannot be atomic with a host journal. Compare/write/readback narrows
races, and interrupted non-idempotent effects remain uncertain rather than
replayed. Actual savestate/session detection needs a verified native epoch; the
candidate snapshot's pointer-stability counter is diagnostic only. Never use a
heap address as stable save identity. No code patch runs without a verified
I-cache/JIT invalidation executor. No user's existing Wii save is reset or deleted.
