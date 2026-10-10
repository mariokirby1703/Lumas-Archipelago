# Sonic Colours (Wii) setup

PAL `SNCP8P`, revision 0, Archipelago 0.6.7+ and 64-bit Dolphin are required.
Install `requirements.txt`, build the APWorld, and place it in Archipelago's
`custom_worlds` directory. Restart the Launcher and choose **Sonic Colours (Wii)
Client**. A source checkout already loads the world; avoid duplicate packages.
An empty Dolphin window is not running emulation.

## Install the four native Gecko codes

Stop emulation and enable Cheats in Dolphin. The supplied
[SNCP8P_capsule_refresh.ini](../data/SNCP8P_capsule_refresh.ini) contains four
separate Gecko codes: **AP PAL live coloured capsule refresh** and **AP PAL
authoritative progression**, and **AP PAL speed and White Boost gates**, and **AP PAL Egg Medal pickup capture**.
Add and enable all four in the PAL game's Properties
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

## Generate a new schema-4 seed

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
story/Game Land instances; opened actors are never reset. `boost_lock: false`
preserves ordinary vanilla Boost. With it enabled, the native ordinary-use
query requires White Boost Wisp; the gauge is not repeatedly emptied. The
separate native Boost provider remains untouched. The new gates still need
live Normal/Super Sonic validation.

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
New Rings filler rolls 1–100 once per receipt and persists the roll before
delivery. Legacy +10/+25/+50 item IDs retain their old fixed meanings.
Half Boost Refill adds half the actual native maximum, capped at full;
the original captures use maxima of 100 in story Acts and 50 in Game Land.
It fills the gauge even without White Boost Wisp. With Boost Lock enabled, the stored gauge remains unusable for ordinary Boost until that item arrives.
Four useful Progressive Game Land Speed items appear when Game Land is used.
They raise the maximum selectable/simulation speed from 1 to 5; lower speeds
remain selectable. No extra speed YAML option is needed.
`/sonicitems` explains receipt states; `/sonicrecover skip INDEX` abandons one
uncertain attempt. Keep the journal rather than deleting receipt history.

Music `per_world`/`anywhere` redirects the native 36-normal-Act cue table at a
safe attributed map, taking effect on the next load. Off restores vanilla cues.
An optional separate seed CPK extends this to compatible title/menu, map,
boss and Game Land BGM, including the mandatory intro. See
[resource setup and validation limits](stabilization.md). Audible playback still
needs live testing; generating a resource copy does not install it in Dolphin.
Level randomization, Death Link and swimming traps currently require Off.

Commands: `/sonic`, `/sonicstatus`, `/sonicdebug`, `/sonicitems`,
`/sonicnewgame`, `/sonicrecover`, `/sonicmusic`. Status distinguishes detection, journal,
AP transport, counter writes, capsule/progression hooks and music.
See [validation limits](gameplay_overhaul.md) before interpreting a readback
or offline test as proof of an in-game effect.
See [October 10 changes and live evidence](oct10_validation.md) for this build.


## Schema 5, Egg Medals and Terminal Velocity

Regenerate a new seed with this world. Schema-4 slots are rejected; journals are
retained under their original seed/slot-data identities. Existing saves are not
converted to another seed. Terminal Velocity Access's item ID is retired and
other IDs are unchanged. Terminal Velocity unlocks automatically with all eight
AP Wisps and cannot be a Starting Act. Its unlock is not the goal: the default
goal still needs the final boss and Terminal Velocity Act 2 escape.

`egg_medal_sanity: true` adds 21 individual Game Land Egg Medal locations.
The fourth Gecko code captures each native pickup before the actor is removed;
a guarded client arms only the validated ORC instance in the bound playthrough.
Events remain latched across stage exit, then enter the durable pickup journal
and ordinary LocationChecks/acknowledgement transport. They require neither a
Clear nor saving. Game Land stage Ring gates remain, and medal traversal logic
conservatively requires all eight Wisps until individual routes are verified.

Update the capsule code too. It includes White ghost/interaction projection,
separate from the White grant/use gates. Receiving White refreshes an unopened
capsule on its native update without restarting the Act. Opened capsules are
never reconstructed. These new native behaviors need in-game testing.
