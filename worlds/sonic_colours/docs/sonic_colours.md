# Sonic Colours (Wii)

This Archipelago world supports **Sonic Colours PAL SNCP8P, revision 0** in
Dolphin. Each player receives a small `.apsoniccolours` patch. The local
installer builds a separate playable ISO from that player's original game.
No manual Riivolution or AP Gecko configuration is required. Start with
[the installation guide](setup.md).

## Progression and goals

The original New Game introduction still runs before the first save selection.
Connect the client before starting it. World Access items, coloured Wisps and
optional ability items then control the available routes. Story Clears and
native rank results become Archipelago checks; collecting an item does not
substitute for actually clearing its location.

Choose one goal:

- **Nega-Wisp Armor (Final Boss):** clear the boss and the subsequent Terminal
  Velocity Act 2 escape.
- **All Bosses:** complete the required boss clears.
- **All Red Rings:** collect all 180 physical Red Rings across attempts,
  independently of the Red Ring Checks option.

Terminal Velocity requires all Wisps required by the seed's lock options; White
Boost is required only when White Boost Wisp Lock is enabled. Its native order
remains Act 1, final boss, Act 2. Retired Game Land/Super Sonic goal values in
older supported seeds are not reassigned to new goals.

## Options

| Group / YAML option | Behavior and current default |
| --- | --- |
| Progression: `goal` | Final Boss by default; alternatives above. |
| `world_progression` | `unlock_acts_in_order` (default) opens the next Act after a clear. `all_acts_then_boss` opens all six Acts with the world; all six must be cleared before its boss. Legacy `sequential` and `open_acts` names remain accepted. |
| `boost_lock` | On. Require White Boost Wisp for ordinary White capsule/enemy Boost gains. AP Boost Refills remain usable. This does not lock the other Wisps. |
| `movement_unlocks` | On. Ability items control movement, including progressive crouching/sliding, rails, skydiving, stunts and breathing. Off grants the complete ordinary abilities. |
| `super_sonic` | Off. Add seven Chaos Emerald items to unlock optional Super Sonic; this is not a goal. |
| Checks: `red_ring_checks` | `singles` by default; `per_level` checks collecting all five in an Act, or `off`. These physical pickups differ from AP Red Ring currency. |
| `rank_checks` | Off. Select a minimum S/A/B/C grade, or `all` for each grade. Better actual native ranks satisfy enabled lower ranks; score estimates alone do not award rank checks. |
| `one_up_sanity` | Off. Add checks for the 31 validated story 1-Up objects. |
| `wisp_discovery_checks` | On. Seven first coloured-Wisp discovery checks; discovery does not itself grant AP ownership. |
| Game Land: `game_land_checks` | On. Add 21 stage Clear checks and enable AP Red Ring gate currency. This is the master toggle for the subordinate Game Land checks. |
| `eggman_heart_sanity` | On, effective only with Game Land Checks. One native Eggman Heart pickup check per stage. |
| `chaos_emerald_checks` | Off, effective only with Game Land Checks. Check clearing each three-stage group; this does not grant the matching AP Emerald item. |
| `game_land_requirement_reduction` | 0–99%, default 50%. Reduce AP Red Ring stage costs. Game Land 1-1 remains initially available. Old option revisions retain their original absolute-reduction interpretation. |
| Traps: `trap_percentage` | 10%. Percentage of remaining filler slots replaced with weighted traps. |
| `ring_loss_trap_weight` | Medium; remove the applicable normal Sonic ring counter. |
| `score_reset_trap_weight` | Low; reset current level score, preserving saved records/ranks. |
| `dead_weight_trap_weight` | Low; block Jump for 30 gameplay seconds. Menus, pauses and loading do not consume gameplay time. |
| Miscellaneous: `music_randomization` | On. Seed-based music shuffle; see below. |
| `death_link` | Off. Share deaths with other DeathLink players, with deferred safe-state delivery and echo suppression. Remaining live coverage is listed below. |

The Wisp pool depends on both locks. With Ability Locks off, Drill, Hover and
Spikes each have one complete normal unlock. With Ability Locks on, each has
two progressive copies. There are exactly **7 / 8 / 10 / 11 Wisp items** for
(Ability, Boost) locks (off, off) / (off, on) / (on, off) / (on, on).

Disabling Game Land Checks also disables Eggman Heart and Chaos Emerald
checks and removes AP Red Rings, Random Capsules, Assist Change and Progressive
Game Land Speed from the pool. The separate Super Sonic option remains separate.
Random Capsules is Useful normally and Progression when Capsule Sanity is on.

`wisp_capsules: true` is a supported hidden YAML option, omitted from standard
templates and the options creator. It adds eligible individual capsule checks;
ordinary fast pickup coverage still needs more live testing. The hidden
`native_feature_tests` setting is a development aid, not proof of verification.
DeathLink and Dead Weight can be selected without it.

## Items, HUD and music

Filler/effects include Rings, 1-Up, Half Boost Refill and Full Boost Refill.
Deliveries and checks use persistent receipt journals and native acknowledgement
where applicable. Unsafe scenes defer effects. In Game Land, effects target
normal Sonic's inventory even while Assist is active; this is intentional.

The always-on item HUD shows up to five recent messages, left aligned with
outlines and item-class colours. Own finds use “Found your own” and the item
name on separate lines. Messages last 60 seconds with a final ten-second fade,
unless displaced by newer items. Native bonus displays are retained. HUD scene
support includes Acts, maps, Game Land and appended results/menu resources;
some scene coverage still needs visual verification.

New seeds use music mapping version 2. The 80-track donor pool includes
**Reach for the Stars** and **Speak with Your Heart** for ordinary music
destinations. Their original opening/credits uses remain finite. A native audio
engine restart handles full-song repetition without re-encoding; both songs'
restarts were heard and confirmed in Dolphin. Old version-1 seeds keep their
original mapping. The popup uses the seed's playback mapping and the names in
`data/music_display_names.json`; repeated native loop starts are suppressed.
User-adjusted music layout, fonts, colours and timing are preserved.

## Logic and verification limits

The prepared 298-location Sheet Logic V2 dataset is used by the world, including
OR-of-AND routes, progressive counts, option-dependent abilities and individual
Red Ring, 1-Up and Heart requirements. Advanced Logic stays separate; ambiguous
or undocumented Normal routes use conservative rules. This does not establish
that every route has been completed live.

Successful live tests include connected item HUD delivery, World Map display,
story/1-Up checks, Game Land ring loss and normal-Sonic item targeting, Score
Reset, ordinary Dead Weight Jump lock/release, and two-client incoming and
enemy/pit DeathLink cases. These are individual observations, not blanket
production verification.

Still requiring broader Dolphin coverage:

- Breathing timing on water entry, bubbles, resurfacing, respawn and transitions.
- Rapid capsule pickup capture without stopping before each capsule.
- Initially empty Game Land Emerald visibility and all newly unlocked Act
  models; some available Acts may still appear black until a refresh.
- DeathLink drowning/Assist/transformation/Super cases, reconnects and duplicates.
- Dead Weight rails, Wisps, transitions, repeated traps and softlock safety.
- Audible music identity, fades and HUD coverage across every scene and reconnect.
- Actual end-to-end item/check latency and occasional severe short stalls.

A reported Game Land 5-1 crash damaged an injected entry instruction. The current
ISO reserves the observed low-memory word and relocates executable entries;
one connected passage then succeeded, with the relocated instruction intact.
The writer and the associated short lag spike remain unidentified. Host writes
to protected entries are blocked and logged. This is containment with a narrow
live success, not a complete crash-free guarantee. Live-validation flags remain
false where the broader matrix is incomplete.

## Development and distribution

Run `python -m pytest worlds/sonic_colours/test` for the complete world suite.
Private original files under ignored `notes/` support optional native regression
tests; keep them locally and never package them. The ten bounded PAL trace
fixtures live in `test/fixtures/pal_traces/`. Research-audit output belongs under
the repository's ignored `build/`, not in documentation.

Build with `python worlds/sonic_colours/build_apworld.py`. The release contains
the runtime and required local patcher tools, not tests, private notes, dumps,
caches, development reports or old archives. The source has two canonical
documents. For the stock Archipelago WebHost's fixed game-info convention, the
builder additionally generates `en_Sonic_Colours_Wii.md` from this page; it is a
compatibility alias, not a separately maintained guide. Tutorial links use
`setup.md`. Use the built APWorld for WebHost deployment.

Distribute the APWorld and player patches only. Generated ISO/CPK/DOL images
contain original game resources and must stay local. Current item/location IDs,
supported seed schemas, save binding and journals are retained.
