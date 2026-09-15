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

`--local-player 1..4` chooses whose persistent checks and currency are tracked. World locks are enforced
for every local golfer because the game's multiplayer menu can allow a world if any golfer has it.
Use **one AP client per Dolphin instance**. Local golfers share that AP world's access; this is not
independent AP slots for four golfers in a single emulator. HIO results are attributed only on the selected
golfer's turn, and minigame results require the controller's player-root pointer to match that golfer.

## Saving and reconnecting

Keep the same dedicated game profile for the seed. Save normally in-game before closing Dolphin.
Persistent shop, secret and Barker flags are reconciled on every poll, so a purchase missed at the instant
it happens is still sent later or after reconnect. Hole Complete, Par, HIO and minigame checks are recorded locally as soon as
observed and retried until the AP server acknowledges them. These transient checks must be played while
the client is connected; a result already open when attaching is deliberately not attributed to a new run.

Currency receipts and observed checks are stored under Archipelago's user-data directory in
`carnival_games_minigolf/<seed-team-slot-player-hash>.json`. Keep this directory with your game saves.
Reconnecting or restarting the client does not grant processed coins again. Another client cannot open
the same journal concurrently. Do not switch game profiles mid-session or load old emulator save states:
the game does not expose a verified save-profile identifier in the supplied RAM map, and an old save can
discard already delivered currency. The client cannot make game saving and a disk journal atomic.

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
Counter modes place 150% of the configured requirement in the pool, rounded up, while the access or
victory threshold stays at the configured value. Barker Coins Required accepts values from 1 through 50.

Every Par-or-better location can award one of three same-named Par Club Piece items for its world through AP. With Shop Checks
enabled, all 27 pieces are progression items. Shop tiers count only the three received AP pieces of that world:
0/1/2/3 pieces make the cheapest 2/4/6/7 purchases reachable; the Club reward requires all three.
The client clears all 27 Vanilla piece flags during normal holes, minigames, and the level-completion screen,
including a piece Vanilla just awarded. It projects received AP pieces only while the gameplay session pointer
is null, which the live dump identifies as the Pro Shop context.
The completion-screen guard prevents a newly earned Vanilla piece from combining with two received AP pieces
and immediately granting the Club reward. The AP inventory remains authoritative; the Wii save never owns
progression pieces permanently.

The actual purchase/earned-prize byte must be exactly 1 to send its shop check. The client tests this persistent
state in every valid local-player root every poll, without requiring a gameplay session or a 0-to-1 transition.
During gameplay the configured local profile selects the player root; `session + 0x2EC` is not treated as an AP
profile selector. In the Pro Shop, where the session pointer is null, the client scans the two persistent root
slots directly and skips empty slots. Loading transitions with no
valid root pause RAM synchronization until the next poll without resetting the AP connection or receipt journal.
MEM1 (`0x80000000`–`0x817fffff`) and MEM2 (`0x90000000`–`0x93ffffff`) are both valid. If an individual MEM2
live-object read fails temporarily, the client skips live hole/minigame tracking for that poll while continuing
persistent root, location, lock, and item synchronization through a valid fallback root.
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
Traps remove 5, 10, 20 or 50 coins and never reduce a balance below zero. Their relative weights are
**4 / 3 / 2 / 1**, making the largest loss rarest. Receipt journaling prevents a reconnect from applying
the same trap twice. Barker Shop logic budgets the 27 natural collectibles cumulatively
across purchases, so optional filler is never required to buy its full inventory.

Very small check pools may not fit the selected Barker requirement plus the world unlocks, especially
before a gated final world. Generation rejects such a configuration with the maximum feasible requirement;
enable more checks or reduce `barker_coins_required`.

## Validation status

Win + Perfect Checks creates two separate locations for every minigame: `- Win` and `- Perfect`.
A Perfect result sends both; Perfect-only mode generates no Win locations.

World generation, item fill, goal logic and mocked RAM behavior have automated coverage. The supplied
executable was hash-verified and runtime signatures were derived from it. A complete live Dolphin
playthrough, all minigame mappings, multiplayer menu behavior and real save/reload currency timing still
need in-game QA. The master notes identify eight minigame VTables as static mappings and Mine Shaft
Madness as previously live-confirmed. This package does not claim a completed live playthrough.
