# Carnival Games MiniGolf

Archipelago world and Dolphin client for the PAL Wii release of Carnival Games MiniGolf (`RG9P54`).

The world randomizes access to the game's nine worlds and adds checks for normal holes, Par scores,
Hole-in-Ones, minigames, Barker Coins, secrets, and shop rewards. It supports All Holes, Goal World,
and Barker Coin Hunt goals.

## Playing

- [Setup Guide](docs/setup_en.md)
- [Game and Options Overview](docs/en_Carnival%20Games%20MiniGolf.md)
- [Example Player YAML](examples/CarnivalGamesMiniGolf.yaml)

Archipelago 0.6.7 or newer, Dolphin, and the PAL `RG9P54` game are required. Only single-player with local
golfer 1 is supported. Use a fresh in-game profile for each generated seed.

## Building

From the repository root:

```powershell
.venv/Scripts/python.exe worlds/carnival_games_minigolf/build_apworld.py
```

The resulting file is written to `build/apworlds/carnival_games_minigolf.apworld`.

To install it into a standard Archipelago installation while backing up an existing copy:

```powershell
.venv/Scripts/python.exe worlds/carnival_games_minigolf/build_apworld.py `
  --install C:/ProgramData/Archipelago/custom_worlds
```

## Testing

```powershell
$env:AP_TEST_WORLDS = 'carnival_games_minigolf'
$env:SKIP_REQUIREMENTS_UPDATE = '1'
.venv/Scripts/python.exe -m pytest worlds/carnival_games_minigolf/test -q
```

The runtime verifies the supported game and executable revision before writing Dolphin memory. Item and
location IDs remain stable across option choices, and currency delivery uses a local receipt journal to avoid
reapplying confirmed items after reconnecting.
