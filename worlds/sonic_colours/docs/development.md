# Development report — 2026-10-09

## Release status

**Not complete and not ready for gameplay.** The source contains a generating
APWorld, external client and guarded write implementation. Real game permission
hooks and persisted check readers remain unresolved. Default generation produces
explicitly marked research seeds; no live PAL gameplay write is enabled.

The branch `Sonic-Colours-Wii-AP` was created from the current
`Carnival-Games-MiniGolf-AP` checkout. Changes are confined to `worlds/sonic_colours`;
no other world or shared core was changed. A PR should target that actual base to
avoid including unrelated existing game commits. No release claim follows from
the tests below, and no remote publication has been performed.

## Implemented

- Stable game string `Sonic Colours`; local namespace 847000000 with separate
  item and location ranges. Repository search found no existing use of this base.
  This is a custom allocation, not a public upstream reservation.
- Independent packaged catalogs: 66 mission slots, 45 story clears, 21 Game Land
  clears, 180 canonical Red Rings and 706 capsule instances. Static IDs distinguish
  slot, mission, assets and progress records. Six alternative-layer rings remain
  included; the duplicate Sweet Mountain index is excluded by supplied catalog.
- All requested YAML keys, native Toggle/Choice/Range/DeathLink classes, option
  groups, example, compatibility rejection, slot schema validation and `.apsonic`.
- AP item pool, exact counter packing, exhaustive gate calculation, region model,
  goals, optional reward checks, and filler-only trap replacement with half-up
  rounding. Unsupported feature modes are rejected explicitly.
- Machine-readable logic override table (246 entries: 66 clears and 180 rings).
  Unknowns use `all_wisps`; to avoid self-locking, current research generation
  precollects all eight permissions. When all relevant requirements are known,
  individual Wisp items return to the pool. Current stage accessibility is an AP
  research model, not a proof of native map traversal or seed beatability in Wii.
- CommonContext client, launcher/file/URI handling, password/name/nogui options,
  status/debug/recovery commands, ordered item-history barrier and reconnect guards.
- Durable atomic/fsynced journals, exclusive process locks, receipt consistency,
  interrupted-effect refusal and explicit skip recovery. Checks are journaled and
  retried until server acknowledgement, rather than assuming one send was received.
- Actual DME byte reads/writes, BE typed helpers, pointer checks, extra save flags
  dereference, packed flag RMW, compare/readback checks, revision text hashes and
  default-deny address policy. No production adapter can arm a save yet.
- Windows MEM2 fallback adapted from Create: one process, one verified MEM1/MEM2
  alias pair, bounded guest-to-host translation, ReadProcessMemory and
  WriteProcessMemory. Its platform behavior has not been exercised against live RAM.
- Testable no-echo DeathLink state machine, durable remote suppression, bounded
  pending policy, gameplay-time temporary trap lifecycle and restoration failures.
  These are protocol/lifecycle implementations without verified native hooks.
- Offline stage/music planning and default-deny PPC patch manager. No injected
  PPC instructions, CPK repacking or playback replacement are claimed implemented.
- Deterministic APWorld builder using zip-safe resource reads, excluding all notes,
  test inputs, tools, ELF, DOL, CPK and RAM captures.

## Validation

Run from repository root in PowerShell:

```powershell
$env:AP_TEST_WORLDS='sonic_colours'
.venv/Scripts/python.exe -m pytest worlds/sonic_colours/test -q --disable-warnings
.venv/Scripts/python.exe worlds/sonic_colours/tools/audit_research.py
.venv/Scripts/python.exe worlds/sonic_colours/build_apworld.py
```

The test suite verifies catalog integrity, stable IDs, all 180 reductions, all
181 counter targets in four packing strategies, YAML/example generation, checks,
goals, memory reads/writes and failures, save refusal, restart/duplicate/uncertain
journals, protocol history synchronization, trap restoration and DeathLink no-echo.
Six settings each fill 100 deterministic seeds (600 successful AP-model fills).
Nine unsupported settings each reject 100 seeds precisely (900 expected refusals).
Test counts and final commands are recorded in `validation.txt`.

| Research mode | Story | Game Land | Emerald rewards | Physical Red Rings | Total |
|---|---:|---:|---:|---:|---:|
| Default singles | 45 | 21 | 7 | 180 | 253 |
| Per-level | 45 | 21 | 7 | 36 | 109 |
| Red Rings off | 45 | 21 | 7 | 0 | 73 |
| All optional checks off | 45 | 0 | 0 | 0 | 45 |

Rank candidate IDs reserve 44×5 entries, excluding the unverified final-boss
candidate. Rank generation stays blocked, so 44 is not presented as confirmed
native eligibility. Wisp discovery IDs also stay inactive.

A Dolphin process and installed DME were found locally. The read-only hook attempt
returned `is_hooked=False` (status 2), so no game memory could be inspected.
**Zero live writes and zero live game checks have been verified.** Fake-backend
write tests and original ELF opcode comparisons are separate evidence.

## Live operations and blockers

| Operation | Implemented offline | Live status / next proof |
|---|---|---|
| Save selection | Static pointer resolver | Confirm 0x808F3628 chain and UI Slot 1 mapping across restart |
| Progress bit write | Packed RMW + bounds + readback | C semantics, save freshness and allowed write targets unverified; production policy rejects |
| Ordinary Rings / 1-Up | Two-phase queued effect with comparison | Stable stats pointer, caps and synchronization with native duplicate fields unverified |
| Ring Loss Trap | One-shot queued zeroing | Same stats blocker; no active native delivery |
| World access | AP regions/items | Query-layer permission hook unresolved; A/B are not asserted unlock semantics |
| Wisp access / White Boost | AP inventory and logic | Global permission and scripted Cyan tutorial denial unresolved; 0x80055E98 is a load |
| Game Land gates | Exact AP counter and 21 thresholds | Native query source unresolved; no overwriting physical Red Rings |
| Emerald / Super Sonic | Seven AP item identities + permission item | Native ownership query unresolved; 0x8027E744 is a load |
| DeathLink | Protocol state machine, default off | Native kill and death/respawn detector unresolved; life decrement is insufficient |
| Swimming | Reversible lifecycle, default off | Entry/exit routine and goal safety unresolved; 0x800381C4 is a load |
| Stage/music shuffle | Deterministic offline planners | Original Lua/index absent, CPK patcher and compatible native playback not implemented |
| Red Ring checks | Independent/per-level predicates | Persistent 180 flags and commit/reload semantics unresolved |
| Rank checks | Threshold predicates and reserved IDs | Saved best rank, actual quality enum and 44/45 availability unresolved |

Start with the small read-only save-chain observation in `ram_research.md`.
Subsequent steps: isolate Act 1 C-bit persistence, then one Red Ring pickup plus
exit/reload, then trace the Cyan tutorial permission query. Each should produce
specific before/after field evidence before enabling the corresponding adapter.

## Remaining risks and limits

External guest-memory writes cannot be atomic with the host journal or with Wii
updates. Compare/write/readback narrows races but does not eliminate them. A crash
between preparing a receipt and confirming it deliberately blocks replay. A future
adapter must detect savestate rollback and pause/session epochs with reliable native
evidence, and bind a stable save identity that is not a recycled heap pointer.
No guessed journal flag is written into the Wii save. No raw RAM scan is run on
every poll. PPC patch execution remains blocked without verified I-cache/JIT cache
coherency and restoration. Windows fallback currently handles MEM2 only; a wrong
DME MEM1 mapping is rejected rather than guessed around.

Tests for live gameplay, native map progression, native start-act selection,
normal-vs-Super-Sonic boost exceptions and actual cross-world shuffle remain
outstanding. All eight Wisp permissions starting precollected is temporary,
explicit compatibility behavior, not the intended finished randomization.
