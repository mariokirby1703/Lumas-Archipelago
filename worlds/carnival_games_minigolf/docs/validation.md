# Validation record — 2026-09-14

- 76 tests and 1093 subtests passed across the world/client tests and relevant AP general tests before
  the final packaged integration test.
- All 63 world/denomination combinations deliver the correct currency amount. A deterministic 10,000-roll
  sample verifies the requested frequency ordering, with 50/100-coin bundles making up the majority.
- All 36 world/trap combinations deduct the correct 5/10/20/50 coins, clamp at zero, and survive reconnects
  without a second deduction. Deterministic samples verify the configurable trap rate and 4/3/2/1 weighting.
- Every starting world tested with All Holes, Barker Hunt, and both Goal World access modes.
- 30 additional randomized option configurations, including six two-slot multiworlds, filled and beatable.
- Default YAML generated successfully through the normal `Generate.py` path: 179 locations/items,
  multidata, spoiler and `.apcgm` in the resulting ZIP.
- Real local AP server/client handshake tested, including an empty initial inventory. Simulated game RAM
  supplies all default checks; every received item arrives and the server accepts goal completion.
- Receipt journal reopened after full item delivery; coin balances did not change on replay.
- APWorld manifest accepted by `APWorldContainer`; client and launcher registration imported directly
  from the archive with the source world excluded.
- User-provided European DOL matched the master-notes SHA-256; four code-region hashes guard runtime writes.
- Installed `ArchipelagoGenerate.exe` 0.6.7 (frozen Python 3.13.11) successfully generated the default
  seed using the installed APWorld. Its output also passed the real-server protocol smoke test.
- Installed launcher dispatched both client help and a headless startup; the client initialized and
  reached `Waiting for Dolphin`, then exited through the standard `/exit` command.
- A separate five-Barker Goal World seed completed a real server/client protocol run. The threshold
  location was checked, Goal World Access was received from the server, Barker Shop locations were absent,
  and victory occurred only after the three Goal World Par checks.

The RAM tests use a memory substitute, not a live Dolphin playthrough. Outstanding live QA includes
all minigames, multiplayer selection, real save/load timing, and normal-coin replay economy. Setup
documentation distinguishes these outstanding checks from the automated results above.
