# Validation record — 2026-09-14

- 69 tests and 777 subtests passed across the world/client tests and relevant AP general tests.
- All 63 world/denomination combinations deliver the correct currency amount. A deterministic 10,000-roll
  sample verifies the requested frequency ordering, with 50/100-coin bundles making up the majority.
- All 36 world/trap combinations deduct the correct 5/10/20/50 coins, clamp at zero, and survive reconnects
  without a second deduction. A deterministic 20,000-roll sample verifies the 10% trap rate and 4/3/2/1 weighting.
- Every starting world tested with Par, Barker Hunt and both final-world goal combinations.
- 30 additional randomized option configurations, including six two-slot multiworlds, filled and beatable.
- Default YAML generated successfully through the normal `Generate.py` path: 151 locations/items,
  multidata, spoiler and `.apcgm` in the resulting ZIP.
- Real local AP server/client handshake tested, including an empty initial inventory. Simulated game RAM
  supplied 151 checks; all 151 received items arrived and the server accepted goal completion.
- Receipt journal reopened after full item delivery; coin balances did not change on replay.
- APWorld manifest accepted by `APWorldContainer`; client and launcher registration imported directly
  from the archive with the source world excluded.
- User-provided European DOL matched the master-notes SHA-256; four code-region hashes guard runtime writes.
- Installed `ArchipelagoGenerate.exe` 0.6.7 (frozen Python 3.13.11) successfully generated the default
  seed using the installed APWorld. Its output also passed the real-server protocol smoke test.
- Installed launcher dispatched both client help and a headless startup; the client initialized and
  reached `Waiting for Dolphin`, then exited through the standard `/exit` command.

The RAM tests use a memory substitute, not a live Dolphin playthrough. Outstanding live QA includes
all minigames, multiplayer selection, real save/load timing, and normal-coin replay economy. Setup
documentation distinguishes these outstanding checks from the automated results above.
