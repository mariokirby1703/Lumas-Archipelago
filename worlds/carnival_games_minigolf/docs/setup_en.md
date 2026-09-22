# Carnival Games MiniGolf Setup

Use Archipelago 0.6.7 or newer and Dolphin with your own Wii copy of Carnival Games MiniGolf.
This client supports the European **RG9P54** executable whose `main.dol` SHA-256 is
`0aad886672197ff23c2c85beafc4ead58541e75c975593b55558b8fb7d18f251`.
Other releases are refused before the client writes game memory.

1. Copy `carnival_games_minigolf.apworld` into your launcher's `custom_worlds` folder and restart the launcher.
2. Put a player YAML in `Players`. An example is included at `examples/CarnivalGamesMiniGolf.yaml`.
3. Generate and host the multiworld normally. Extract your `.apcgm` file from the generated output ZIP.
4. Open **Carnival Games MiniGolf Client** in the launcher, or open the `.apcgm` file through the launcher.
5. Enter the server address and connect using the slot name in the YAML. The `.apcgm` supplies the name
   and seed identity; the server supplies authoritative options and checks. Connecting without the file also works.
6. Boot the supported game in Dolphin. Use a **new, dedicated game profile for each AP seed**.
   Wait for the client to report active synchronization before selecting a world.
7. Play normally. The client opens your starting world and received worlds, sends checks, grants currency,
   and reports victory automatically. AP item messages appear in the client window.

The launcher normally supplies `dolphin-memory-engine` (also used by Create and Marbles).
For a source checkout, install `worlds/carnival_games_minigolf/requirements.txt` into the same Python
environment that runs Archipelago. No game patch, Gecko code or replacement DOL is required.

## Commands and local players

- `/connect host:port` connects to the AP server; `/disconnect` stops synchronization.
- `/dolphin` reports emulator and executable verification status.
- `/minigolf` shows unlocked worlds, received Barker Coins and checks.
- `/missing` uses the standard AP check listing.

The client defaults to local golfer 1. From source, use:

```powershell
.venv/Scripts/python.exe -m worlds.carnival_games_minigolf.client.launch --name Golfer --connect localhost:38281 --local-player 1
```

Only **single-player / local golfer 1** is supported (`--local-player 1`). Local multiplayer
result ownership is not verified. Checks, currency, pieces and world locks use only the selected root;
a secondary pointer does not establish an active multiplayer profile. Use one AP client per Dolphin instance.

## Saving and reconnecting

Keep the same dedicated game profile for the seed. Save normally in-game before closing Dolphin.
Persistent shop, secret and Barker flags are reconciled on every poll, so a purchase missed at the instant
it happens is still sent later or after reconnect. Hole Complete, Par, HIO and minigame checks are recorded locally as soon as
observed and retried until the AP server acknowledges them. These transient checks must be observed while the client is connected. A visible result is reconciled
when its hole or minigame context can be identified; a popup alone cannot identify a minigame.

Currency receipts and observed checks are stored under Archipelago's user-data directory in
`carnival_games_minigolf/<slot-data-team-slot-player-hash>.json`. Keep this directory with your game saves.
Reconnecting or restarting the client does not grant processed coins again. Another client cannot open
the same journal concurrently. Do not switch game profiles mid-session or load old emulator save states:
the game does not expose a verified save-profile identifier in the supplied RAM map, and an old save can
discard already delivered currency. The client cannot make game saving and a disk journal atomic.

The journal key hashes canonical slot data plus team, slot and local golfer. Version 0.3.14 refuses to
silently replace a matching legacy journal: finish an existing seed with the previous client, or use a newly
generated seed and dedicated game profile. This prevents accidental receipt replay during the key migration.

Currency waits for a null session and unchanged menu state 2/root for at least 300 ms. The client persists
intent, writes the balance, then waits at least another 300 ms before committing the receipt on a later poll.
If the game restores the old balance, the write is retried and confirmation restarts. Loading, gameplay,
shop and root changes do not count as stable menu confirmation. This improves writeback handling but
is not proof of durable Wii-save storage; real save/reload timing still needs live validation.
An interrupted grant is recovered automatically when the current balance equals its before/after value.
If the balance is ambiguous, synchronization pauses. `/currency_recover skip` keeps the current balance
and marks that receipt delivered; `/currency_recover apply` retries that receipt against the current balance.
These commands affect only the pending grant. World unlocks and goal-counter Barker totals are reconstructed
from AP's complete received-item history and periodically reasserted.

## Goals, Goal World access, and Par Club Pieces

- **All Holes:** finish all 27 normal holes. Score and Par do not matter.
- **Goal World:** receive Goal World Access, then finish all three holes in the selected Goal World on Par or better.
- **Barker Coin Hunt:** receive the configured number of AP Barker Coin items.

`goal_world_access` controls the Goal World item. `world_unlock_item` puts the generic progression item
**Goal World Access** in the normal pool. `barker_coins` locks that same item on the internal
**Barker Coin Goal Requirement** location. Once the configured number of Barker Coin items has arrived,
the client checks that location; the AP server sends Goal World Access; only receipt of that item physically
opens the Goal World. Reaching the Barker threshold itself is not victory.

Starting World and Goal World list only the nine worlds and default to Archipelago's standard `random`
value. Goal World must differ from Starting World; if both resolve to the same world,
the generator rerolls Goal World from the other eight.

Barker counter modes automatically remove Barker Shop checks. Local collectible Barker Coins do not
advance the AP counter. In normal mode they remain spendable, as do received Barker Coin filler items.
Counter modes aim for 150% of the configured requirement, rounded up, capped by available item slots.
Only the required number are progression; surplus coins are useful. Feasibility before Goal World uses
the required number, not the surplus. Barker Coins Required accepts values from 1 through 50.

Every Par-or-better location can award one of three same-named Par Club Piece items for its world through AP. With Shop Checks
enabled, all 27 pieces are progression items. Shop tiers count only the three received AP pieces of that world:
0/1/2/3 pieces make the cheapest 2/4/6/7 purchases reachable; the Club reward requires all three.
The client clears all 27 Vanilla piece flags during normal holes, minigames, and the level-completion screen,
including a piece Vanilla just awarded. Menu state 2 displays checked Par locations; shop candidate state 3
projects received AP pieces once per visit. Temporary display writes and their removal do not set the dirty
flag. Clearing unprojected Vanilla pieces during gameplay remains a persistent change.

**Pro Shop detection remains experimental.** State 3 is a candidate, not a verified unique shop screen.
World Select, Level Select and actual Pro Shop dumps are still needed to identify a reliable screen object.
Avoiding dirty writes does not prevent the game itself from saving a displayed projection during another
save operation. Permanent save isolation needs live verification before a public release.

The actual purchase/earned-prize byte must be exactly 1 to send its shop check. The client tests this persistent
state in the configured AP profile root every poll, without requiring a gameplay session, a 0-to-1 transition,
or AP access to that world. Other local roots cannot inject checks into the AP slot.
During gameplay the configured local profile selects the player root; `session + 0x2EC` is not treated as an AP
profile selector. In the Pro Shop, where the session pointer is null, the client scans the two persistent root
slots directly and skips empty slots. Loading transitions with no
valid root pause RAM synchronization until the next poll without resetting the AP connection or receipt journal.
MEM1 (`0x80000000`–`0x817fffff`) and MEM2 (`0x90000000`–`0x93ffffff`) are both valid. If an individual MEM2
live-object read fails temporarily, the client skips the failed read while continuing
persistent root, location, lock, and item synchronization through the selected root.
Normal-hole identity is derived from the MEM1 hole-definition table. Completion is reconciled only while the live
`in_goal` field equals 1, so `session + 0x2F0` is no longer mandatory. Minigame identity
comes from the controller VTable, with manager-state-7 fallback only for Hole A. The latch survives
controller/session loss and result transitions, retiring after five consecutive menu polls or a new normal
hole in gameplay state 5. Result pointers and hole-definition records are read in blocks; unreadable objects
are skipped individually. Normal Complete/Par/HIO detection does not require a controller read.
Outside manager shop state 3, Vanilla Par Club Piece flags are checked before the client clears them.
Game-to-AP checks and Starting World lock enforcement continue while the received-item history is loading.
Only inventory-derived writes such as currency replay, Barker counter reconstruction, threshold evaluation, and
Par Club Piece projection wait for the complete ordered history.
The client also requires Dolphin Memory Engine to report active emulation. A process hook without a running game
can expose stale Wii RAM; that state is never read for locations or written to and reports that it is waiting for
the game to start.
Logic assumes normal coins can be earned through repeated play in an open world;
Coin Bundles are assistance, not required progression. Each world has separate bundles for 5, 10, 20,
50, 100, 200 and 500 coins. Their relative weights are **1 / 2 / 8 / 16 / 16 / 6 / 4**: approximately
1.9% / 3.8% / 15.1% / 30.2% / 30.2% / 11.3% / 7.5% of generated bundles. Worlds are chosen uniformly.
In normal mode, 10% of filler rolls produce a spendable Barker Coin instead; counter modes use only
normal Coin Bundles and traps for filler. Trap Weight controls the percentage of filler rolls that produce a world-specific Coin Trap.
Trap Weight defaults to 0 (opt-in). Traps remove 5, 10, 20 or 50 coins and never reduce a balance below zero. Their relative weights are
**4 / 3 / 2 / 1**, making the largest loss rarest. Receipt journaling prevents a reconnect from applying
the same trap twice. Barker Shop logic budgets the 27 natural collectibles cumulatively
across purchases, so optional filler is never required to buy its full inventory.

Very small check pools may not fit the selected Barker requirement plus the world unlocks, especially
before a gated final world. Generation rejects such a configuration with the maximum feasible requirement;
enable more checks or reduce `barker_coins_required`.

## Validation status

The nine main minigames support Win and Perfect locations; a Perfect result sends both when enabled.
Devil's Brew - Spiders supports **Win only** and is experimental. Its CSpidersSubLogic VTable is distinct
from Ghoul Hunter, but use of the standard results popup for Spider completion is still an assumption.
The synthetic test validates that assumption's implementation, not the live game behavior.

Earlier live reports include Mine Shaft Madness, Ghoul Hunter, G-Nome Project and Pterodactyl's Run.
Their source dumps are not available in this checkout. The other five main minigames, Spider completion,
unique shop identity and 500-coin save/reload behavior still need live testing. No complete live playthrough
or multiplayer support is claimed. See [validation.md](validation.md) for current automated results and
[release_checklist.md](release_checklist.md) for the remaining evidence required before release.
