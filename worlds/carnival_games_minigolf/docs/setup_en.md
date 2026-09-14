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
Persistent flags are read again on reconnect. HIO and minigame checks are recorded locally as soon as
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

## Goals and economy

- **All 27 Holes on Par:** earn every Par Club Piece. There is no duplicate generic Par check.
- **Barker Coin Hunt:** receive the configured number of AP Barker Coin items.
- **Barker Goal World Requirement:** receive the configured Barker Coins, unlock the selected/random final
  world, then complete its three holes on par. This final-world finish takes precedence over `goal`.

Barker counter modes automatically remove Barker Shop checks. Local collectible Barker Coins do not
advance the AP counter. In normal mode they remain spendable, as do received Barker Coin filler items.

Normal purchases use the agreed ascending-price tiers: 2/4/6/7 available in logic after 0/1/2/3 obtainable
Par pieces; the Club reward requires all three. The actual purchase/earned-prize flag is still required
to send a shop check. Logic assumes normal coins can be earned through repeated play in an open world;
Coin Bundles are assistance, not required progression. Each world has separate bundles for 5, 10, 20,
50, 100, 200 and 500 coins. Their relative weights are **1 / 2 / 8 / 16 / 16 / 6 / 4**: approximately
1.9% / 3.8% / 15.1% / 30.2% / 30.2% / 11.3% / 7.5% of generated bundles. Worlds are chosen uniformly.
In normal mode, 10% of filler rolls produce a spendable Barker Coin instead; counter modes use only
normal Coin Bundles and traps for filler. Ten percent of filler rolls produce a world-specific Coin Trap.
Traps remove 5, 10, 20 or 50 coins and never reduce a balance below zero. Their relative weights are
**4 / 3 / 2 / 1**, making the largest loss rarest. Receipt journaling prevents a reconnect from applying
the same trap twice. Barker Shop logic budgets the 27 natural collectibles cumulatively
across purchases, so optional filler is never required to buy its full inventory.

Very small check pools may not fit the selected Barker requirement plus the world unlocks, especially
before a gated final world. Generation rejects such a configuration with the maximum feasible requirement;
enable more checks or reduce `barker_coins_required`.

## Validation status

World generation, item fill, goal logic and mocked RAM behavior have automated coverage. The supplied
executable was hash-verified and runtime signatures were derived from it. A complete live Dolphin
playthrough, all minigame mappings, multiplayer menu behavior and real save/reload currency timing still
need in-game QA. The master notes identify eight minigame VTables as static mappings and Mine Shaft
Madness as previously live-confirmed. This package does not claim a completed live playthrough.
