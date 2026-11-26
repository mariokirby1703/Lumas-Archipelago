# Assignment identity and entitlement pass — 26 November 2026

**Partial implementation. The requested native pause-menu selector, chapter activation, Open World initialization and synchronous mission-entry hooks are not implemented. This is not an acceptance-complete delivery.**

## Implemented code

- `tools/research_assignment_entries.py` extracts all 15 indexed original replay hotspots, map pins, city story jobs, callbacks, cutscenes and destination doors from `GAME4/jobs/scripts/city_setup/level_transitions/level_transitions.sf`. It rejects incomplete arrays, duplicate callback indices and assignment/destination mismatches. `bridge/assignment_entries.json` contains derived metadata and the source hash, not proprietary scripts.
- `bridge/assignment_policy.py` reconstructs independent entitlements from canonical item IDs, the active slot's effect table and received AP receipts. Unknown identities, mismatched bindings and wrong item names cannot grant permissions. This is a diagnostic policy evaluator, **not** an installed native gate. Native acknowledgement remains false.
- `bridge/client_journal.py::assignment_policy` reconstructs that policy from durable journal receipts after restart. No separate permission cache is trusted. The journal's existing per-seed binding isolates receipt histories. Native profile/scene enforcement is still missing.
- `catalogue.json` adds the two missing canonical Blackwell access items. The existing shared Blackwell item and every previous item/location ID are retained. `tools/build_ap_catalogue.py` preserves the two additions on regeneration. Ordinary Story Access generation remains rejected because native enforcement is absent; these items are not falsely advertised as functional progression.
- `bridge/goals.py` fixes an eager dictionary-default lookup that raised KeyError for valid assignment-only completion records. Unknown completion rows do not satisfy the final goal.

## All 15 assignments

Each key has its corresponding `Story Access: <key>` entitlement. Their original callback and door identities are recorded in `bridge/assignment_entries.json`.

| # | Assignment | Key |
|---|---|---|
| 1 | Some Assaults | rooftops |
| 2 | Trouble in Stir | prison |
| 3 | Miner Altercation | mine |
| 4 | Kung Fool | temple |
| 5 | Dirty Work | bank |
| 6 | Astronaughty | space_centre |
| 7 | Scrapyard Scrap | scrapyard |
| 8 | The Colossal Fossil Hustle | museum |
| 9 | Hot Property | fire_station |
| 10 | Smash 'n' Grab | blackwells_mansion_1 |
| 11 | They All Scream for Ice Cream | icecream_parlour |
| 12 | High Steal | construction_site |
| 13 | Disruptive Behavior | secretbase |
| 14 | Breaking and Reentering | blackwells_mansion_2 |
| 15 | Fly Me to the Moon | moon_base |

## Native investigation and remaining implementation

The original `generic_inviteotherplayer.sf` enters its one-shot StartLevel state and sets the invite job's StartLevel Bool. The mission-specific `mine.sf` consumes that Bool and changes to TriggerDoor. The centralized replay script uses a separate original callback/summary path. No native admission hook covering these paths has been installed. Denial/rearm behavior is therefore unimplemented, not synthetically declared passing.

Further disassembly of pause drawer lookup `0x799e0` shows calls into `0x319bf0` and `0x312700`, returning through the caller-provided object. This is not evidence of a safe button allocator or callback lifetime contract. No guessed UI callback or signature was installed. Original frontendmain/fe_button_04 assets remain unmodified. Chapter activation, persistent chapter context, markers and Open World setup retain their previous unsupported status.

See [TODO](TODO.md) for the outstanding native work. Specifically, the policy evaluator must not be attached only to the final door trigger: the original invite state would already be consumed. All replay, story, summary and automatic entry paths need a proven pre-consumption admission point.

## Verification and delivery

Commands (exit 0):

```
.venv/Scripts/python.exe worlds/lego_city_undercover/tools/research_assignment_entries.py
.venv/Scripts/python.exe -m unittest discover -s worlds/lego_city_undercover/tests
.venv/Scripts/python.exe worlds/lego_city_undercover/tools/simulate_generation.py --count 180 --output build/lego_city_undercover/assignment_fills_20261126.json
```

425 test executions: 418 passed, seven skipped. 180/180 logical fills passed. New tests cover each of the 15 independent entitlement decisions, wrong permission, duplicate receipt, reconnect, cross-seed isolation, stale binding and wrong effect mapping. They do not prove native admission or UI rendering.

Package output remains `build/lego_city_undercover/lego_city_undercover.apworld`, version 0.0.1. Both archive filenames passed ZIP import and restrictive-fill smoke tests (exit 0). Existing launcher: `build/lego_city_undercover/StartLCUNativeClient.cmd`. The build tool compiled and verified `LCUItemBridgeTests_eae25d8c39839683.dll` and updated the manifest; native feature source is unchanged. No UI patch exists, and no new menu functionality is available to test. No running-game validation, save mutation or game-file patch was performed in this pass.
