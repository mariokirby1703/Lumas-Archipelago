# Validation record ? 2026-09-20

Version 0.3.14, local working-tree validation. This record does not claim a GitHub Actions run or live playthrough.

## Automated results

- **110 tests and 846 subtests passed**, with the two existing environment warnings (optional `_speedups`
  extension unavailable; source Python 3.11.9 version warning).
- Test selection: `worlds/carnival_games_minigolf/test` and AP general `test_groups`, `test_options`,
  `test_ids`, `test_items`, `test_locations`, `test_names`, `test_world_manifest`.
- Covers all bundle/trap denominations and worlds, all starting worlds/goals, 30 randomized option
  configurations including six two-player AP multiworlds, fills and beatability. AP multiworld testing does
  not mean local Dolphin multiplayer is supported.
- Added regressions for a late popup after controller/session loss, unreadable objects before a valid popup,
  consecutive menu latch retirement, Hole-A-only fallback, controller-independent Complete/Par/HIO,
  delayed receipt commit, game writeback retry, loading with a null session, interrupted confirmation,
  non-dirty UI projections, secondary roots, strict uninitialized-memory failures, small Barker pools,
  canonical slot-data journal identity and safe rejection of legacy receipt journals.
- Barker surplus is useful, and small pools cap surplus while retaining the required progression count.
- Source `Generate.py` completed the default example (179 checks/items) and Barker Goal World fixture
  (182 total checks/items, including the locked threshold check). Both archives passed real loopback
  AP server/client handshake, all checks/items, accepted goal, fully drained receipt journal and reconnect.
- Deterministic APWorld build completed; manifest, archive imports, bundled client initialization and
  launcher registration passed the package smoke script with the source world excluded.
- Installed to `C:/ProgramData/Archipelago/custom_worlds` with an automatic backup of the previous archive.
  Installed `ArchipelagoGenerate.exe` 0.6.7 successfully generated the default example; that archive also
  passed the real-server protocol smoke test (179 checks/items).
- `git diff --check` passed.

Commands (PowerShell, repository root):

```powershell
$env:AP_TEST_WORLDS='carnival_games_minigolf'
$env:SKIP_REQUIREMENTS_UPDATE='1'
.venv/Scripts/python.exe -m pytest worlds/carnival_games_minigolf/test test/general/test_groups.py test/general/test_options.py test/general/test_ids.py test/general/test_items.py test/general/test_locations.py test/general/test_names.py test/general/test_world_manifest.py -q
.venv/Scripts/python.exe Generate.py --player_files_path worlds/carnival_games_minigolf/examples --outputpath build/carnival-games-minigolf/v0314-generation --seed 20260920 --spoiler 1
.venv/Scripts/python.exe Generate.py --player_files_path worlds/carnival_games_minigolf/test/fixtures --outputpath build/carnival-games-minigolf/v0314-barker-generation --seed 20260920 --spoiler 1
.venv/Scripts/python.exe -m worlds.carnival_games_minigolf.test.protocol_smoke build/carnival-games-minigolf/v0314-generation/AP_57696350233222392309.zip
.venv/Scripts/python.exe -m worlds.carnival_games_minigolf.test.protocol_smoke build/carnival-games-minigolf/v0314-barker-generation/AP_57696350233222392309.zip
.venv/Scripts/python.exe worlds/carnival_games_minigolf/build_apworld.py
```

Local logs are under `build/minigolf-*.log`. Packaged output is
`build/apworlds/carnival_games_minigolf.apworld`; generated seed archives are in the directories above.

## Limits and outstanding evidence

All RAM tests use synthetic memory. No Dolphin process was running, and the previous live dumps exist
only in a separate ChatGPT conversation, not in this workspace. No capture-derived fixture or new live
confirmation is claimed. The optional strict fake rejects missing initialized bytes; it does not make
synthetic fixtures evidence of actual game layout.

State 3 remains a provisional Pro Shop detector. Spider completion via the standard results popup is
unconfirmed. Five main minigames still lack the earlier reported live confirmation. The 500-coin grant,
real save/reload persistence and possible game-initiated saving of temporary piece projections require
live testing. Avoiding the dirty flag is not a guarantee against those saves.

Only single-player/local golfer 1 is supported. A public release is pending the evidence listed in
[release_checklist.md](release_checklist.md). Historical master notes are explicitly non-authoritative.
