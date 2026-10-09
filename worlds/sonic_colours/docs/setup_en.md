# Sonic Colours setup (PAL research build)

This is a custom, unfinished integration (`ap-status=Custom`). It generates
research seeds, but **cannot yet play a complete multiworld**. Native save/scene
identification, permissions and persisted checks are blocked. An APWorld package
is not a game patch; putting it in Archipelago does not randomize the Wii game.

## Requirements

- Your own Sonic Colours Wii European disc, game ID `SNCP8P`, revision 0.
- Archipelago 0.6.7 or later and Dolphin on a supported 64-bit host.
- Python environment matching Archipelago with `dolphin-memory-engine` installed.
- Original executable matching SHA256
  `92aefe33b577493b492f8433ca68b90d25d29d2f6d9c85310a6829481281f8a9`.
  The client compares both mapped text sections, as well as region and revision.
  Modified executables and other regions fail verification.

From a source checkout:

```powershell
.venv/Scripts/python.exe -m pip install -r worlds/sonic_colours/requirements.txt
.venv/Scripts/python.exe worlds/sonic_colours/build_apworld.py
```

The library is [py-dolphin-memory-engine](https://github.com/randovania/py-dolphin-memory-engine).
Do not confuse it with the standalone RAM editor. Its Python import is
`dolphin_memory_engine`. A running Dolphin process alone is insufficient: the
game must be emulating. Close additional Dolphin instances before future writes.

For a packaged Archipelago installation, put the built
`build/apworlds/sonic_colours.apworld` in `custom_worlds` and restart Archipelago.
Keep only one copy of the world; a source checkout already has it in `worlds`.

## Save protection

Back up your Wii save through Dolphin's Wii save export workflow before testing.
Manually create a **fresh visible Save Slot 1** for each seed. Never delete a
valuable file to make room; use a separate Dolphin user directory if necessary.
The client never creates, resets or erases saves.

The selected index byte is not yet mapped to visible UI slots. The current build
therefore refuses to arm even if the byte is zero. User confirmation alone cannot
bypass this restriction. Future arming requires verified UI slot mapping, at least
two independent freshness fields, stable scene context and a seed-bound save
identity. Local journals live in Archipelago's `sonic_colours_journals` directory.
They are external files, not hidden Wii flags. Savestate/session changes disarm
the guard; non-idempotent effects need explicit recovery when their result is
uncertain.

## Generation and client

Use [SonicColours.yaml](../examples/SonicColours.yaml) as the option template.
The game string is exactly `Sonic Colours`. The defaults produce 253 checks.
Generated `.apsonic` files contain slot metadata, not Wii executable patches.
The spoiler and slot data explicitly mark every seed `research_only`.

Until the user supplies clear/ring logic, unknown entries conservatively require
all eight Wisps. To avoid bootstrap self-locks, research generation precollects
all eight AP Wisp permissions and reports this compatibility behavior. Individual
Wisp progression is therefore not active in default research seeds yet.

Launch **Sonic Colours Client** from Archipelago Launcher, open a generated
`.apsonic`, or run:

```powershell
.venv/Scripts/python.exe -m worlds.sonic_colours.client.launch --nogui --connect localhost:38281 --name SonicPlayer
.venv/Scripts/python.exe -m worlds.sonic_colours.client.launch path/to/player.apsonic --nogui
```

`archipelago://` URLs and the usual `--password` argument are supported. The client
can authenticate with an AP server and attempt to hook Dolphin. Gameplay polling
currently stops at `save_slot_mapping_unverified` after revision verification.

Commands: `/sonic`, `/sonicstatus`, `/sonicdebug`, and `/sonicrecover skip INDEX`.
Debug prints a small JSON status and candidate pointer chain. It does not dump
RAM. Recovery skips an interrupted effect without replaying it; an ordinary
pending receipt cannot be skipped as though it had been applied.

## Feature limits

World/Wisp/Emerald access and Game Land gates are represented in AP logic but
their native permission writers are unresolved. Ring filler, 1-Ups and Ring Loss
Trap stay queued. Physical Red Rings never credit the AP Red Ring inventory.

Non-off level/music shuffle, rank checks, DeathLink, Wisp discoveries, swimming
and the Super Sonic goal fail generation with `requires_verified_hook`. No CPK
is modified, no Gecko code is installed, and there is no temporary patch to
revert in this build. Native swimming restoration must be proven before enabling
that feature; the original cheat is known to cause goal softlocks.

See [development](development.md) for the exact remaining live checks.
