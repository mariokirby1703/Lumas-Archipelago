# Testing

Executed: `python -m unittest discover -s worlds/lego_city_undercover/tests -v`.
Twenty tests passed: known RC4 vector, CRC normalization, path traversal rejection,
invalid PE headers, synthetic CC4 index association/bounds, ZIPX/DFLT chunks, duplicate mission rejection,
runtime symbol hashes, synthetic objective records/bits and uninitialized objective manager.
These verify tools, not gameplay. No AP generation, networking, item grant or notification tests exist yet.

Real-file checks: all 14 files inventoried and SHA-256 hashed; all ten indices parsed with payload bounds;
76,582 of 76,584 names CRC-matched; 1,779 selected files extracted and revalidated byte-for-byte on rerun;
92 side-mission rows and 1,059 scanner rows parsed. Capstone identified ten action getter names and candidate methods.
No separate QuickBMS extraction has been used as an independent oracle.

Git check-ignore confirmed original EXE/DAT and extracted level table are ignored.
The repository virtual environment successfully used Utils.read_apignore/match_tree_files to confirm no notes,
EXE, DLL, DAT or SAV entered the candidate package file list. No release package was built.

Windows diagnostics successfully reported game_not_running. Steam launch attempts reached RunningInstallScript
in Steam's console log, then successfully launched. An outside-sandbox read verified the running EXE hash,
ASLR-resolved module header and the 51-entry ability symbol table. The main-menu candidate state arrays were all zero.
All 51 symbols were matched to executable strings with uppercase FNV-1; snapshot and mappings remain in notes/analysis.
No gameplay transition, item effect or completed objective was observed. Native UI interaction is unavailable through these tools.

Next live experiment:

1. Complete Steam first-run prerequisites and launch the game normally.
2. Run `python worlds/lego_city_undercover/bridge/diagnose.py`; expect module_header_read for the recorded hash.
3. Create a dedicated test save, complete the vanilla opening, quit, and preserve the complete slot externally.
4. Record displayed currency, equipped class and one named objective. Save clean baseline copies.
5. Collect only that objective, save/quit, and compare; repeat after restart and on another test slot.
6. Establish the corresponding runtime engine object using the static action references and a debugger.
7. Verify reads across loads/transitions before implementing any grant. Validate engine calling context before writes.

Do not use the candidate method RVAs as direct ctypes calls or guess script-context objects.
There is no playable first test seed to run yet.

Additional offline verification: 662 jobs / 1,577 defaults round-trip byte-for-byte; 745 scripts indexed;
947 v17 GIZ resources passed section bounds validation, ten other headers were explicitly excluded.
New tests cover malformed/duplicate job fields, comment/string-safe script calls, variable evidence, GIZ bounds,
ability-query semantics, mocked objective pointer relocation/change/short reads and deterministic diagnostic packaging.
The standalone .pyz was invoked with -I and --help to verify imports without the source working directory.
Its allowlist contains three bridge modules, an entry point and a manifest; no game assets or dumps.
The complete research_pipeline.py --with-disassembly completed successfully with fresh original-file hashes.

Inventory continuation: 28 tests pass, including 64-bit Stud balances, checkpoint separation, all three
Super Brick selector branches, character defaults versus pending grants, category aliases, page-bounded strings,
full mocked character traversal and changing statistics pointers.
The new --inventory package was actually run against the supported game with -I; it read 17,590 Studs and
2,177 Super Bricks after a 17,580/2,171 baseline, exactly matching the user. The three primary outfit candidates
matched the reported roster. Bank-only character state was insufficient; pending grants were necessary.
No item grants, writes, purchases or restart persistence were tested.
The build allowlist now includes four Python bridge modules plus generated factual collection_manifest.json,
an entry point and its manifest. No original scripts, saves, binary assets or memory dumps are included.

Actor/story continuation: 32 tests pass. Added tests cover concrete JobValue type/hash checks, a full mocked
named-job traversal, both context-index branches, active model validation, key presence/removal and cyclic lists.
The actual paused game supplied COP, M02_Dspot_key_item and Default context. All 662 job hashes were
resolved by the research probe. Five selected jobs were read through the built .pyz.
No engine method was invoked. The actor model and key-presence transition remain to be compared live.
