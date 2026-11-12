# Implementation status

Status as of 2026-11-11. This is research tooling and a read-only diagnostic, not a playable release.

| Feature | Implementation | Static validation | Automated tests | Live tests | Problems / next action |
|---|---|---|---|---|---|
| File inventory | Implemented | Full hashes of 14 files | PE rejection tests | Not applicable | Preserve originals |
| Archive indexing | Implemented for supplied CC4 v2 | 76,584 entries; 76,582 CRC names | Synthetic bounds/CRC tests pass | Not applicable | Two unnamed entries |
| Targeted extraction | Implemented ZIPX/DFLT | 1,779 files, 10,768,902 bytes | RC4 vector and chunk tests pass | Not applicable | No independent extractor comparison |
| Location candidates | Implemented research reports | 92 mission / 1,059 scanner rows | Duplicate mission validation | None | Map persistent flags; filter clues/dead data |
| Items / abilities | Query semantics decoded; no grants | IsAbilityUnlocked checks existing OR pending; lock/unlock event actions identified | Query semantics test passes | Main-menu raw state only | Verify game-thread call interface and gameplay gating |
| Logic / options / APWorld | Not implemented | AP 0.6.8 APIs inspected | None | None | Requires genuine checks and grants |
| JobDataMap / save parsing | Resource defaults parsed; no save reader/writer | 662 jobs / 1,577 fields, byte-exact round-trip | Bounds, types, defaults and duplicates pass | No save comparison | Establish serialized save layout and marker semantics |
| Process detection | Implemented Windows read-only | Win32 APIs bound explicitly | Absent-process path exercised | Game process and exact hash verified | Sandbox blocks process reads; outside-sandbox read succeeded |
| Memory read | Header and experimental ability snapshot | Exact hash; all 51 symbol hashes match | Symbol profile test passes | Main-menu snapshot succeeded | Compare in loaded save and across transitions |
| Automatic checks | Experimental objective reader; no AP transmission | 12-byte records / completion bitset derived statically | Synthetic records, bits, null manager pass | None | Observe one persistent completion |
| Currency reading / writing | Stud and Super Brick readers implemented; no writer | Profile balance distinguished from checkpoint; mode-dependent brick getter | 64-bit values, branch modes and pointer changes tested | 17,580/2,171 to 17,590/2,177 matched | Test other save/scene modes and spending; no writes |
| Disguise unlocks / gating | Not implemented | Class grants in scripts | None | None | Preserve story safety; reconcile vanilla grants |
| Story progression | Research only | Act/job variable names | None | None | Map chapters and final goal |
| Client networking / seed identity | Not implemented | CommonClient reviewed as repository API | None | None | Build after proven game bridge |
| Notifications | Not implemented | UI action method candidate | None | None | Verify text format, Unicode and thread context |
| Launcher / Windows EXE | No AP client; separate standalone diagnostic .pyz built | Explicit source allowlist; no assets | Reproducible archive build test passes; isolated --help runs | No new live test | Dedicated AP client remains outstanding |
| Packaging | Ignore rules implemented | Git and AP ignore checks passed | Actual Utils parser exercised | Not applicable | No APWorld artifact yet |
| Mod compatibility | Unknown | No original files patched | None | None | Investigate proxy and asset overlap |

Steam launch was requested through its installed client. The console log reached RunningInstallScript;
the game subsequently launched. An outside-sandbox read verified its hash and module header.
A main-menu snapshot read all 51 ability hashes and two zero-filled candidate state arrays.
All hashes match uppercase FNV-1 names from the executable. No menu interaction was automated.
A loaded-save comparison is deferred while the user is away; this is not completed gameplay verification.

Offline continuation: 745 scripts / 2,654 selected calls indexed; 143 scanner IDs have possible setter evidence.
947 of 957 GIZ resources have bounded v17 section parsing; ten are explicitly unsupported.
Full research pipeline passed with 20 tests and fresh full-file hashes.
Artifact: build/lego_city_undercover/LegoCityUndercoverDiagnostics.pyz (requires 64-bit Python 3.11+).

Live follow-up: first controllable harbour scene captured. All 1,059 runtime objective record hashes match
scanner definitions. Duplicate SwapBrown records are explicitly excluded. No completed-objective transition
has been observed yet. Intro cutscene skipping is now a requested comfort feature, still under investigation.

Inventory milestone: --inventory now reads profile Studs, mode-selected Super Bricks and the Gold Brick counter.
A controlled collection matched +10 Studs and +6 Super Bricks in the built isolated .pyz.
Primary character candidates matched civilian Chase, police Chase and Grace; pending grants are combined with bank
state while co-op defaults, vehicles and customizer models remain separate. Equipped-character recognition,
token-versus-purchase transitions, save-slot detection and restart persistence remain unverified.
The collection resource confirms 305 progress characters and 120 vehicles. Twenty-eight tests pass.
See research/inventory_layout.md for exact evidence, addresses and limitations.

Paused-key milestone: actor_reader.py reads equipped model, attached-object definitions and current context.
The live key entry M02_Dspot_key_item was present; context was Default and model COP.
story_reader.py reads concrete typed fields from the real 662-job registry; MainframeActive=true.
The rebuilt diagnostic contains --actor and --story. Thirty-two tests pass.
No key-use, reload, detective-context transition or lock/write has been validated.

Autosave/exit observation: Police Chase and Grace moved from pending queues into bank bit/byte state,
without changing the three effective primary unlock candidates. Reader handles this transition; an AP detector
must deduplicate it. Story job advanced to Act1_Mission=2, Act1_Stage=1. Disk/reload validation is still outstanding.

User requirement clarified: AP owns individual character unlocks; native collectible acquisition sends a check
and must suppress its vanilla character reward. AP receipts must be applied and natively saved immediately,
without depending on a future story autosave. See character_randomization.md. Existing state readers alone
cannot distinguish native discovery from AP grants and are not an implementation of this behavior.

Existing-slot reload validated: 19,030 Studs, 2,186 Super Bricks and all three bank-owned primary outfits
remained present while a station-exit cutscene replayed. Global queried abilities matched. Story checkpoint
values differed; repeated notifications must not be interpreted as new pickups. AP grants/saving remain unimplemented.

User requirement: received AP characters must be fully owned and usable without a vanilla purchase.
Other suitable shops should sell seed-placed AP items, showing their actual server-reported names and
recipients before payment. Each purchase is a single priced check; local receipt handles self-owned items.
Shop UI, scouting, purchase transactions and character grants are not yet implemented.
