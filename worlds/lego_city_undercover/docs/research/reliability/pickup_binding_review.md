# Pickup proof review and native writer guard

Follow-up to commit 858453cee, 15 November 2026. No item/location IDs or version settings changed.

## Implemented

The reader now mirrors the additional native condition at RVA 0x9a693a–0x9a6948: the stats pointer at 0x1c7a830 must exist and its byte +0x335d must be nonzero before the city persistence branch is used. This is described only as the native city-writer gate, not a guessed named gameplay ability. Type flag 0x4000000, instance flag !0x200, grid/index bounds and stable scene/bank checks remain required. The gate is read again at the end of the snapshot. The pickup's collected flags are also rechecked: 0x9a690e sets the collected bit before invoking the pickup callback, while 0x9a6ad3–0x9a6adf can clear it on rejection. An in-progress change must not become stable collection evidence.

Inactive city persistence does not erase the separate native_collected observation used for mission objects. It does not invent a mission save bit. Mission-specific persistent registration remains a TODO.

Version 2 journal proofs retain both stable registration observations, exact source/resource/type, instance identity, measured native grid width, tile coordinates, original branch flags, writer gate, process hash and journal identity. A metadata refresh preserves any earlier observed collection transition. This is structural verification, not a live gameplay verdict.

`tools/review_journal_bindings.py` accepts copied collectible-evidence JSON or opens SQLite journals read-only. It verifies the actual evidence fields rather than trusting the verification label. It reconstructs the native bit formula from measured dimensions, verifies exact typed source uniqueness, rejects known/quarantined bits and collisions with both incoming and packaged records, and never overwrites an existing mapping.

The default operation is review only. `--register` explicitly requests an atomic shared-catalogue merge, guarded by an exclusive registration lock and a comparison against the file originally reviewed. A stale .json.lock is not deleted automatically; inspect it before manual removal after a crashed reviewer. Game processes, saves, server receipts and journals are never modified by this tool.

## Usage from the repository root

```
.venv/Scripts/python.exe worlds/lego_city_undercover/tools/review_journal_bindings.py --journal PATH_TO_BINDING.sqlite3
.venv/Scripts/python.exe worlds/lego_city_undercover/tools/review_journal_bindings.py --input collectible_evidence.json --require-collection
.venv/Scripts/python.exe worlds/lego_city_undercover/tools/review_journal_bindings.py --input collectible_evidence.json --register
```

The default report is build/lego_city_undercover/next_pass/journal_binding_review.json. `--require-collection` additionally requires an observed false-to-true pickup-bit transition; this still does not prove every visual gameplay property. Multiple --input and --journal arguments are supported, with conflicts blocking promotion rather than choosing a winner.

Old proofs remain readable for existing client state. They cannot be newly promoted without complete current evidence. Fresh observations upgrade their metadata while preserving earlier collection observations. After shared registration, restart the source client; regenerate the APWorld for distribution. Source keys and numeric AP IDs are unchanged, so binding additions alone do not require a new seed.

## Actual coverage

The game was not running during the probe. The inspected journals contained zero recorded binding proofs. No shared bindings were promoted: coverage remains 40/471 city sources, with 431 unresolved. Synthetic tests cover the complete observer-to-review-to-atomic-registration path, malformed and incomplete proof rejection, duplicate source identities, concurrent registration, collection evidence preservation and the native writer-gate transitions.

Validation: all 386 unittest executions passed; the packaged APWorld imported with a beatable restrictive fill. The native DLL sources are unchanged and the existing versioned binary remains verified. Logs: build/lego_city_undercover/next_pass/binding_review_full_tests.txt and journal_binding_review.json.

The new APWorld was installed in C:/ProgramData/Archipelago/custom_worlds after preserving and hash-checking the previous archive in build/lego_city_undercover/installed_backups. Version remains 0.0.1. No save or active AP receipt was modified.
