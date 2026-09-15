# Carnival Games MiniGolf for Archipelago

World, Dolphin client and build tool for Wii Carnival Games MiniGolf (RG9P54).

See [Setup](docs/setup_en.md) and [Game overview](docs/en_Carnival%20Games%20MiniGolf.md).
The original technical handoff is preserved in `notes/` and is not shipped in the APWorld.

Build from the repository root:

```powershell
.venv/Scripts/python.exe worlds/carnival_games_minigolf/build_apworld.py
```

Output: `build/apworlds/carnival_games_minigolf.apworld`. The archive contains the client, static data,
options, docs and example YAML. No dependency on Create, Marbles, local game files or the notes folder.
`--install C:/ProgramData/Archipelago/custom_worlds` additionally installs it, backing up an older build.
Restart the launcher after installation.

Tests:

```powershell
$env:AP_TEST_WORLDS = 'carnival_games_minigolf'
$env:SKIP_REQUIREMENTS_UPDATE = '1'
.venv/Scripts/python.exe -m pytest worlds/carnival_games_minigolf/test -q
```

After generating the example, run the real-server protocol smoke test (with simulated game RAM):

```powershell
.venv/Scripts/python.exe -m worlds.carnival_games_minigolf.test.protocol_smoke build/carnival-games-minigolf/generation/AP_87394597476875360744.zip
```

The smoke test starts an isolated loopback server, completes every default check, verifies all receipts
and goal status, and checks that recreating the client connection does not duplicate currency.

Runtime addresses live in `client/constants.py` and `client/runtime.py`; generation never reads game RAM.
Item and location IDs are stable across options. Coin Bundles contain 5, 10, 20, 50, 100, 200 or 500 coins;
50 and 100 are most common. The relative weights are isolated in `Items.py`.
`Trap Weight` controls what percentage of filler rolls become world-specific -5/-10/-20/-50 Coin Traps;
larger losses are rarer.
Unsupported revisions fail verification before any memory write.
