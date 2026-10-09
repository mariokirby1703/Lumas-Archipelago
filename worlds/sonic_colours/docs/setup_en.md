# Sonic Colours (Wii) setup

PAL `SNCP8P`, revision 0, Archipelago 0.6.7+ and 64-bit Dolphin are required.
Install `requirements.txt`, build the APWorld, and place it in Archipelago's
`custom_worlds` directory. Restart the Launcher and choose **Sonic Colours (Wii)
Client**. A source checkout already loads the world; avoid duplicate packages.
An empty Dolphin window is not running emulation.

## Install both native hooks

Stop emulation and enable Cheats in Dolphin. The supplied
[SNCP8P_capsule_refresh.ini](../data/SNCP8P_capsule_refresh.ini) contains two
separate Gecko codes: **AP PAL live coloured capsule refresh** and **AP PAL
authoritative progression**. Add and enable both in the PAL game's Properties
→ Gecko Codes. Replace the older AP capsule code with this version; preserve
unrelated settings/codes. When pasting an individual code, paste only its hex
lines, excluding INI sections and `$` names.

Alternatively merge the file's `[Gecko]` and `[Gecko_Enabled]` entries into the
existing `GameSettings/SNCP8P.ini`. Do not replace the entire settings file.
The client can export the exact current codes:

```powershell
.venv/Scripts/python.exe -m worlds.sonic_colours.client.launch --export-capsule-gecko build/SNCP8P.ini
```

Gecko installs executable code with Dolphin's normal cache handling. DME only
writes verified data fields. The client checks PAL text hashes and the exact
installed payloads, including return branches. Unknown patches are rejected.
The progression hook is required for immediate native vanilla-grant suppression
and discovery/Game Land event capture. Without it, ordinary check/counter paths
remain available, but native interception is reported unavailable.

## Generate a new schema-3 seed

Use [the default example](../examples/SonicColours.yaml) or
[Luma's migrated configuration](../examples/Luma_Migrated.yaml). Old server
slot data is intentionally incompatible: regenerate the seed and open a new
server room. Never transfer a different seed's journals or receipts.

The YAML migration command writes a separate file and reports changed options:

```powershell
.venv/Scripts/python.exe -m worlds.sonic_colours.client.launch --migrate-yaml OLD.yaml NEW.yaml
```

Removed options: `wisp_unlocks`, `world_unlocks`, `chaos_emerald_items`,
`red_ring_bundle_strategy`. These progression systems always use AP. The new
`wisp_capsules` boolean replaces `wisp_capsule_sanity`; both former enabled
modes migrate to all eligible capsules. Old Emerald names become Green, Red,
Blue, Yellow, Purple, Cyan and White Chaos Emerald, preserving numeric IDs.
`final_boss` becomes `nega_wisp_armor`; `all_game_land` becomes
`all_game_land_stages`. The former `all_story_clears` mode migrates to
`all_bosses`, which intentionally has a different victory condition.

## New Game and checks

Connect to the intended AP room, then start a fresh vanilla **New Game**.
Automatic detection checks native scene/mission, factory flags and fresh rank
records. `/sonicnewgame` is optional and cannot bypass these checks.
The original mandatory Tropical Resort Acts 1 and 2 remain unchanged. Immediate
Red Ring, eligible capsule and completed results-screen Clear/Rank checks work
before the first save-slot selection; they do not require a save or complete
ReceivedItems history. Choose a free slot normally. Keep existing saves.

The client journals checks before transmission and records genuine server
acknowledgements. Death, stage exit and reconnect do not erase physical Red Ring
identities. An existing unrelated save, save switch or rollback stops write
attribution. Back up your Dolphin Wii save before testing.

`starting_act: random` selects among 36 normal Acts, six world bosses and
Terminal Velocity Acts 1/2. Explicit choices remain available. After the intro
save, the selected stage and its path become available without fake clears.
The final boss cannot be a starting stage.

## Items and optional checks

All eight Wisp items are shuffled, with no automatic precollection. Coloured
capsules require their matching AP item. Capsule locations include 680 eligible
story/Game Land instances; opened actors are never reset. White Boost and some
scripted player grants still need a verified native restriction mechanism.

AP Red Ring items are independent of the 180 physical pickups. Game Land stage
1 is free in every group; stages 2/3 use increasing AP thresholds. Reduction 40
requires 140, and the seed contains 187 AP Red Ring value. The pool maximizes
single rings automatically and uses +5/+10 only when capacity requires them.
Excluded checks and precollected progression are accounted for.

Rank checks use minimum S/A/B/C grades: earning a better grade completes lower
enabled thresholds. `wisp_discovery_checks` covers seven native coloured-Wisp
introductions, not ordinary capsule openings. White has no identified native
discovery event and is excluded. Emerald reward checks require all three native
Game Land clears plus an observed native clear transition in that group. A
separate Emerald reward presentation event is not independently verified.

Rings, 1-Ups and Ring Loss Traps use guarded counters/mirrors with later
observations. Rewards received on results screens defer durably to the next
living Act. Uncertain attempts do not replay or block later receipts.
`/sonicitems` explains receipt states; `/sonicrecover skip INDEX` abandons one
uncertain attempt. Keep the journal rather than deleting receipt history.

Music `per_world`/`anywhere` redirects the native 36-normal-Act cue table at a
safe attributed map, taking effect on the next load. Off restores vanilla cues.
Boss/Game Land music remains vanilla; audible playback still needs live testing.
Level randomization, Death Link and swimming traps currently require Off.

Commands: `/sonic`, `/sonicstatus`, `/sonicdebug`, `/sonicitems`,
`/sonicnewgame`, `/sonicrecover`. Status distinguishes detection, journal,
AP transport, counter writes, capsule/progression hooks and music.
See [validation limits](gameplay_overhaul.md) before interpreting a readback
or offline test as proof of an in-game effect.
