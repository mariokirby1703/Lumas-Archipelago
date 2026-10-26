# Sonic Colours (Wii) Archipelago World

Sonic Colours is a Wii platformer in which Sonic explores Eggman's interstellar amusement park and uses the powers of the Wisps. This Archipelago world supports the PAL `SNCP8P` revision 0 release in Dolphin. See the [Setup Guide](setup.md) to get started.

## Goals

- **Nega-Wisp Armor (Final Boss):** defeat the final boss and complete the Terminal Velocity Act 2 escape.
- **All Bosses:** complete the required boss clears.
- **All Red Rings:** collect all 180 physical Red Rings across attempts, regardless of the Red Ring Checks setting.

## Locations

- Story Act and boss clears
- Red Ring pickups or collecting all five Red Rings in an Act
- Optional rank checks
- Optional 1-Up object checks
- Optional first discoveries of the seven coloured Wisps
- Optional Game Land stage clears, Eggman Hearts and Chaos Emerald group clears
- Optional individual Wisp Capsule checks through a hidden YAML option

## Items

- World Access and Wisp unlocks
- Movement abilities, including progressive abilities when Ability Locks are enabled
- White Boost Wisp when its lock is enabled
- Seven Chaos Emeralds for optional Super Sonic
- Red Ring currency for Game Land, Random Capsules, Assist Change and Progressive Game Land Speed when applicable
- Rings, 1-Ups and Boost Refills
- Ring Loss, Score Reset and Dead Weight traps

## Campaign Options

- **Goal:** Nega-Wisp Armor, All Bosses or All Red Rings
- **World Progression:** unlock Acts in order, or open all Acts before the boss
- **White Boost Wisp Lock:** require the White Boost Wisp for ordinary Boost gains; AP Boost Refills remain usable
- **Ability Locks:** put movement abilities in the item pool
- **Super Sonic:** add seven Chaos Emerald items to the item pool

## Check Options

- **Red Ring Checks:** individual rings or all five rings per Act; the current GitHub branch also exposes an Off option, while the supplied documentation describes checks as always enabled. Availability depends on the APWorld version.
- **Rank Checks:** choose which S, A, B and C ranks give checks
- **1-Up Sanity:** add checks for 31 story 1-Up objects
- **Wisp Discovery Checks:** add checks for discovering coloured Wisps
- **Game Land Checks:** add stage-clear checks and enable AP Red Ring currency
- **Eggman Heart Sanity:** add a heart check for each Game Land stage
- **Chaos Emerald Checks:** add checks for clearing each three-stage Game Land group
- **Wisp Capsule Sanity:** hidden YAML option for individual eligible capsules

## Other Options

- **Game Land Requirement Reduction:** reduce stage unlock costs from 0–99%; default 50%
- **Trap Percentage:** percentage of filler replaced by traps; default 10%
- **Trap Weights:** adjust Ring Loss, Score Reset and Dead Weight frequency
- **Music Randomization:** shuffle music; enabled by default
- **DeathLink:** share deaths with other DeathLink players; disabled by default

## Notes

The New Game introduction still begins in Tropical Resort before save selection. Connect **before** starting it so the client can observe checks during the opening Acts.

Physical Red Ring checks are separate from AP Red Ring items used to unlock Game Land stages. Wisp discovery checks do not grant their corresponding Wisp items, and Chaos Emerald checks do not grant the matching Emerald items.

Disabling Game Land Checks also disables its Eggman Heart and Chaos Emerald checks and removes its associated items from the pool.
With Ability Locks enabled, Drill, Hover and Spikes use progressive unlocks; otherwise each has one complete unlock.

## Credits

- **MysticPika:** for doing the majority of the logic.
- **Subna:** for drawing the Logo.
