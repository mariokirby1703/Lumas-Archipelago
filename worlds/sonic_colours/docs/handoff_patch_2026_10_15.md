# Sonic Colours Wii AP: post-Codex fixes (2026-10-15)

Base: user's uploaded `sonic colour.zip`, containing Codex's `cd64ce55` and `6e43e52` work. Checked current remote branch head `6e43e52f4c5d` before patching. This **incremental archive contains only changed/new files**, with paths relative to the `worlds/` directory (`sonic_colours/...`). Do **not** replace the entire source tree with this archive; overlay these files on the existing `worlds/sonic_colours/` package. Do not delete any other files.

## Fixes made here

1. **Sheet V2 Normal OR routes** (`logic_v2.py`): the four reviewed expressions already have properly parsed OR-of-AND route lists. Earlier code incorrectly converted these into AND-of-ALL alternatives, locking legal routes until unrelated Wisps were found. Alternatives now follow their parsed routes. Advanced routes remain disabled. Rank S on Asteroid Coaster Act 4 (`stg650`) now treats "Sidestep and Kill Enemies" as a performance tip, not an excuse to require *all* Wisps and movement abilities. The native result still decides S-rank.
2. **YAML-aware developer test inventory** (`client/test_inventory.py`, `client/runtime.py`, `client/client.py`): `/give wisps`, `/remove wisps`, `/give all` and shorthand `drill`/`hover`/`spikes` respect Boost Lock / Ability Locks by selecting actual normal or progressive Wisp variants. The compatibility fallback for test harnesses without slot options is preserved. These commands alter local test overrides, never server-owned item histories.
3. **Capsule fallback reconciler** (`client/runtime.py`): a verified opened capsule is now compatible with either normal/progressive Wisp items and with vanilla White Boost when Boost Lock is off. This repairs old persisted-event reconciliation without inventing a capsule opening. Native committed opening journal remains the preferred source.
4. **DeathLink echo safety** (`client/deathlink.py`): when an incoming kill request times out, throws, or cancellation is not verified, three subsequent alive polls do not prematurely clear persistent remote echo suppression. A witnessed native death followed by stable recovery still clears the cycle. Cancellation exceptions are surfaced diagnostically rather than aborting the entire poll. Deliberately fail-closed: on truly uncertain remote requests outgoing DeathLinks are suppressed until a native death witness/recovery. Operator diagnostics/restart recovery needs live verification.
5. **Music Popup CPU work** (`client/music_popup.py`): memoize the deterministic global seed/mode mapping (8 entries). Previous code recomputed its recursive 87-cue assignment on every HUD update, including every fade tick. This patch changes **no positioning, fonts, colours, labels, music_display_names.json, durations or HUD mailbox format**.
6. Regression checks added/updated in `test/`.

## Validation performed in this environment

- All changed Python modules compile cleanly.
- Pure logic test: 298 routes x four Boost/Movement combinations are satisfiable with full appropriate inventory.
- `logic_v2` sheet samples verify OR-of-AND and that Advanced routes remain excluded.
- `/give` and `/remove` prior command AST tests: 8 representative cases passed.
- DeathLink existing state-machine tests: 4 passed; additional late-echo and cancellation-uncertain scenarios checked with a standalone harness.
- Capsule normal/White-off alternative check passed in an isolated test harness.
- Music-seed cache: 500 HUD update calls triggered one mapping calculation; changing seed/mode invalidated the entry.

The complete AP unit/integration suite **could not be executed here** because the upload is the `sonic_colours/` subtree and the Archipelago Core (`BaseClasses`, `worlds.AutoWorld`, etc.) is not present in this runtime. The new pytest regressions must be run in your normal Archipelago environment. No Dolphin/PAL ISO live-test was run and no `live_validation` flag was changed.

## Still outstanding: do not call these completed

- The Area Map black locked-looking models for AP-unlocked Acts: Codex established the model-selection boundary but not a safe resource-owning replacement. Changing raw actor pointers without scene refcount/lifetime proof risks crashing the game. Requires PAL native research and live test.
- Progressive Breathing live water-entry, bubble, restart, drowning-level, pause/respawn tests; committed native hooks have unit evidence only.
- Rapid Wisp Capsule pickup capture in Dolphin, notably Aquarium Park checkpoint 1770 and scene transitions. Existing bounded 32-entry journal can overflow.
- Game Land empty Yellow Emerald first-entry visibility/animation remains unverified.
- DeathLink drowning, Game Land, Assist, transformed/Super, reconnect, expiration and overlap; Dead Weight rails/stunts/Wisps/reconnect, 30 gameplay-second timing and softlock matrix. **Do not bypass release gates** to claim production-ready DeathLink/Dead Weight.
- Rings/1-Up/refills/Ring Loss/Score Reset native receipts through game modes and death transitions, Wisp Boost Lock with White missing, end-to-end notification latency.
- Music actual donor/normal-FX branch identity, scenes, results and long-session runtime. The user's HUD positioning and names were preserved.

Run tests, generate **new AP seeds** when altering locations/items/logic (this patch changes logic reachability but not IDs), and build a fresh PAL patched ISO from the unmodified original when changing native resources/hooks. This incremental package does not contain ISO/CPK/DOL files or private research assets.
