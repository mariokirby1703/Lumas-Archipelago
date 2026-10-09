# Current native implementation status

The immediate-pickup implementation and current limitations are documented in
[Immediate checks and native gameplay testing](immediate_checks.md). That report
supersedes the historical save-only Red Ring policy and all-writers-disabled
statements below. No live Dolphin write was verified in this change.

## Historical investigation before immediate pickups

# Native implementation status, 2026-10-09

**This is still not a complete playable AP integration.** The latest read-only
DME probe found Dolphin PID 19212 open with no running emulation; no new live
gameplay, AP roundtrip or native write was verified. The original PAL DOL, CPK and thirteen
MEM1/MEM2 capture pairs under `notes/memdumps_and_more` were used directly.
These results supersede the earlier statements that scene/stats parents and
physical ring storage were entirely unresolved. They do not establish live writes.

## Implemented native reads

All 66 native bank C clear flags are decoded through the existing code-derived
catalog and accessor, covering story and Game Land. Individual live save/reload
proof still covers only the three Tropical Resort missions; the remaining slots
have not been exercised in-game. This is separate from the still-blocked AP send.

The production adapter now resolves application `0x808F336C` -> document at
application+4 -> global module at document+1C -> active context at module+34.
Application/module/context vtables are checked. This path works independently
of a selected save; an unavailable save does not suppress gameplay diagnostics.

Stage state is the native member-function state machine, rather than a life-count
heuristic: gameplay handler `8001CDB4`, result handler `8001EDE4`, death handler
`8001DC40`. Active and underlying handlers must both indicate gameplay before
the snapshot identifies living gameplay. Map context modes distinguish the
captured global map, world map and Game Land selection. Other states remain unknown.
Native scene/player changes reset the stable-poll count.

The mission name comes from stage+4C. Its native map-cell address identifies the
clicked slot. The native stage metadata vector supplies loaded data/path IDs;
for example Game Land 1-1 is mission `stgD10`, with its own underlying data.
Actor ID from stage's actor-state object resolves the player through the bounded,
backlink-checked actor list. Player+8C resolves stats; story and Game Land use
their respective ring/boost objects. Respawn resolves the new actor and addresses.

Native rings, boost, held Wisp and life storage are exposed by `/sonicdebug`.
The native life value in some dumps differs from their approximate operator
labels; no HUD interpretation or life writer is claimed validated by that label.
The ring setter at `800A5850` clamps to 9999; the existing guarded filler code
now uses that actual bound rather than 999. Its production write gate remains closed.

Physical Red Ring storage is code-derived from `8015F16C/8015F18C` and the save
caller at `8016CD1C`: bit `320 + zone*30 + act*5 + ring`, indices zero-based.
All 36 persisted masks are read, with full before/after context checks. Current
pickups come from the native actor state at +91. Current and saved collections
remain separate in snapshots. Only the native save-bank masks contribute to
durable checks and victory; active masks are diagnostic and cannot be credited
permanently before saving. Native save-bank reads do not alone prove a successful
NAND flush; that remains part of the unresolved native save lifecycle. Received
AP Red Ring items never populate these fields.

Rank records are selected-save+AC, stride C, indexed by the actual stage table
accessor `8007F18C`. The byte at record+0 is the awarded/best rank, score is +4,
time is +8. `8019DF48` establishes rank-table indices 0..3=S/A/B/C, 4=D;
the original Lua labels the same four ordered thresholds. Unused records are FF.
The client reads the awarded byte, not a grade inferred from score. Rank YAML
modes now generate and validate; all 44 candidate slots have not been played.

New Game corroboration uses active mandatory Act 1, the exact factory flag
pattern plus native entered bit 90, and untouched rank records. Operator intent
is still required by SaveGuard. This enables the temporary bootstrap journal;
it does not fabricate the missing durable save discriminator.

## Evidence and checks

`test_native_originals.py` runs the production adapter, including the real PAL
executable text SHA checks, over all thirteen original pairs. The pairs are
several seconds apart, not simultaneous captures. No test writes to the originals.

- First Act 1: mission `stg110`, gameplay, 16 native rings, active physical ring 1.
- Act 1 results: native result handler and active mask 17 (rings 1/5).
- Act 2 results: saved Act 1 mask 17, awarded B=2, score 705200, time 12019.
- First map: saved Act 2 mask 26 (rings 2/4/5), B=2, score 613820, time 10226.
- Game Land 1-1: mission `stgD10`, separate stats mode 2, five native rings.
- Act 3 Cyan held: held value 1 and boost approximately 60.6.
- Death: native death handler and stage death count 1; respawn changes actor.
- Final map: saved Act 3 ring 2, B=2, score 662500, time 25042.

Previous live evidence remains limited to the corrected inline save chain and
clear bits 150/151/152 through normal save and title-menu reload. No AP server
acknowledgement or in-game item delivery was verified this turn.

Previous baseline: **474 tests passed**, including original-capture reads and 1,800
filled seeds (100 for every supported rank/music mode combination). This is not
the full requested option matrix: the unimplemented modes below remain rejected.
The rebuilt APWorld imports its native reader, archive patcher, catalogs and
launcher directly from the ZIP and contains no original game assets/captures.
The import smoke test used the repository's `SKIP_REQUIREMENTS_UPDATE=1` setting
to avoid its unrelated bulk installer for other worlds; it did not mock imports.

## Actual music patch workflow

Music modes now have a player-owned archive patch, rather than only a permutation
dictionary. The patcher reads CRI UTF/CRILAYLA, validates PAL CPK SHA256, obtains
cue names from the original `bgm.strm.csb` CUE table, and changes precisely the
36 normal-act BGM strings in `actstgmission.lua`. Cue aliases are deliberately
not mistaken for waveform filenames. Spawn/path/event/rank metadata is preserved.

It copies the archive, appends an aligned uncompressed Lua member, updates its
TOC sizes/offset and content totals, and verifies decompressed readback before
publishing a new file without overwriting either an existing output or the source.
The adjacent JSON manifest records seed, mapping and script hashes.

From the repository, using a generated `.apsonic` whose music option is enabled:

```powershell
.venv/Scripts/python.exe -m worlds.sonic_colours.client.launch "seed.apsonic" --patch-music "original/sonic2010_0.cpk" "patched/sonic2010_0.cpk"
```

Install into a **separate extracted copy** of the owned disc, retaining the
original disc/save. [Wiimms ISO Tools](https://wit.wiimm.de/) supplies extraction
and composition; the documented [EXTRACT](https://wit.wiimm.de/wit/cmd-extract.html)
and [COPY](https://wit.wiimm.de/wit/cmd-copy.html) commands accept this workflow:

```text
wit EXTRACT original.iso sonic-seed --psel DATA --pmode NONE
```

Replace the CPK in that staging directory's `files` tree with the new CPK, then:

```text
wit COPY sonic-seed sonic-seed.iso --iso
```

The real 1.17 GB PAL archive was patched and read back at
`build/sonic-music-validation.cpk`; this artifact is private and excluded from
Git/APWorld. ISO reconstruction and audible playback were not tested. This
workflow does not make the rest of the AP integration playable.

## Remaining implementation blockers

| Feature | Exact remaining gap |
|---|---|
| Seed/save binding, AP check roundtrip, resume/rollback | No durable per-save native discriminator or native first-save-selection transition implemented. A recycled heap pointer, selected index, profile name or mutable playtime is insufficient. Consequently bootstrap events cannot yet be flushed to AP. |
| Native filler and Ring Loss | Real field resolution and existing receipt/write/readback code are present, but durable binding and production write validation remain missing. No native write was performed. |
| Wisp/world unlocks, White Boost, arbitrary starting act | Native permission query redirection is unimplemented. Save flag polling would race vanilla grants; stage startup also explicitly forces the first tutorial Wisp. White Boost refill blocking and Super exemption are unresolved. |
| Game Land gates, Emerald items, Super Sonic | AP-owned counter/threshold and Emerald permission overrides are unimplemented. Physical ring masks cannot substitute for the AP counter. Native Options Satellite/form behavior remains unverified. |
| Capsule sanity and Wisp discovery | Catalog identities exist, but no native capsule-open event has been joined to its exact ORC layer/object/spawn identity. Subtype mapping remains provisional; modes remain rejected. |
| DeathLink | Native death/respawn reads now exist; native incoming kill invocation and protocol-to-game integration remain unimplemented. Modes remain rejected. |
| Swim trap | No safe reversible native state transition, cleanup path or verified invocation exists. The supplied unsafe Gecko code is not installed. |
| Level shuffle | Native mission table and full metadata are resolved, but actual slot rewriting, mandatory-intro exception and persisted check remapping are unimplemented. Modes remain rejected. |
| Rank checks | Saved rank reads and minimum-rank detection implemented; all-slot eligibility/replay improvements and AP acknowledgement remain unverified. |
| Music shuffle | Original archive patch and readback implemented; rebuilt-disc boot and audible playback unverified. |

These are missing production implementations/verification, not completed features
hidden behind a switch. Existing permission/kill/swim stubs and capability gates
remain. No full-playability or successful native write claim is made.

## Follow-up fixes

Follow-up validation: **481 tests passed**, including all thirteen original
capture pairs, packaging manifest verification and a real world-loader subprocess
with both stale installed Sonic copies present. The production Dolphin loop was
also run against the actual installed DME/Dolphin process: it reported `noEmu`,
no verified disc, no read/write/acknowledgement and the correct source paths.
This is connection/diagnostic validation, not an in-game acceptance test.

The client records successful memory accesses with UTC timestamps, and successful
writes only after readback and the final context check. Disc verification records
the observed six-byte ID, revision and text hash failure; it does not replace
the expected PAL verification. Dolphin process candidates and the verified MEM2
fallback PID are distinguished because DME does not expose its selected PID.
An inaccessible or mismatched game disarms the guard and removes the current
snapshot. Historical reads and revision observations remain explicitly timestamped.

`/sonicstatus` shows loaded core code ID, Python/package paths, source commit and
dirty state, or the packaged build manifest and verified file hashes. APWorlds
carry a deterministic content ID and commit attribution. The GUI title includes
the core code ID. Location acknowledgement telemetry comes from server-confirmed
`Connected`/`RoomUpdate` state, never from locally attempted sends. Each unresolved
native operation has its own diagnostic reason.

The checkout's world loader ignores installed Sonic loose/zip copies while the
repository's Sonic source is present, and logs both paths. This prevents an old
`custom_worlds` copy from overriding the development branch. Packaged installations
without the loose source continue using the normal APWorld loader.

Clear checks now require the coherent native save accessor as well as its
matching chain. The older bounded live traces remain useful diagnostic candidates,
but do not falsely satisfy the new accessor's progress verification. A missing
stage table or a switched selected save cannot become verified progress.

Further PAL tracing established that `8016C9B0` appends 16-bit event IDs;
flow 4 dispatches `8016E760`, which builds and starts a movie context via
`802EAC74`. Completing event `0x6E` resets flow to zero at `8016C714`.
Neither flow 4 nor that event is sufficient proof of a save selection. The
initializer at `8015F9F4` also iterates six native slot blocks; identifying their
primary/secondary serialization roles is necessary before placing a durable seed
marker. No speculative save padding or reserved flag bits were written.
