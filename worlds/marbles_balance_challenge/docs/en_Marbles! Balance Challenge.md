# Marbles! Balance Challenge Archipelago World

Marbles! Balance Challenge (PAL, `RK6P18`) and Marble Saga: Kororinpa (NTSC-U, `RK6E18`)
share this Archipelago world and its external Dolphin client. Select `game_region` before generation.
The AP game name remains Marbles! Balance Challenge for both regions. NTSC-U support needs
live Dolphin validation; experimental traps are disabled for that region.

## Goals

- Stump Temple Level 10 Normal
- Stump Temple Level 10 Hard

## Locations

- Level goals
- Kororin Capsules
- Green Gems
- Anthonys
- Trophies
- Tutorial levels
- Wii Balance Board levels

## Items

- World unlocks per difficulty
- Bonus world unlocks
- Hard Mode unlock
- AP-side Stump Temple Piece counter items
- AP-side Green Gem counter items
- Marble unlocks
- Figure Roller Head unlocks
- Vehicle unlocks
- Junk filler items
- Trap items

## Campaign Options

- Goal selection:
  - Stump Temple Level 10 Normal
  - Stump Temple Level 10 Hard

- Included difficulties:
  - Normal
  - Easy + Normal
  - Normal + Hard
  - Easy + Normal + Hard

- Random Starting World
- Tutorial Checks, default off
- Game Region: PAL or NTSC-U
- Wii Balance Board Levels: 100 on PAL, 30 on NTSC-U

## Logic Options

- Green Gem Sanity
- Kororin Capsule Sanity
- Anthony Sanity
- Trophy Sanity:
  - Off
  - Bronze
  - Silver
  - Gold
  - Platinum
  - All

- Hard Mode Unlock:
  - Start
  - Item
  - Green Gems
  - Vanilla

- Required Stump Temple Pieces for Stump Temple Goal World Unlock
- Required Green Gems for Hard Mode
- Extra Counter Item Percentage
- Split Vehicle World Access

## Item Pool Options

- Trap Chance
- Blackout Trap Weight
- Mirror Trap Weight
- Inverse Trap Weight
- Noclip Trap Weight

## Notes

This is an early release of the Marbles! Balance Challenge APWorld.

Kororin Capsules are always included as locations. AP-side Stump Temple Piece items are separate counter items used for Stump Temple access in your selected Goal difficulty. Green Gems can also be used as AP-side counter items when Hard Mode unlock is set to Green Gems. On the World Map on Normal Difficulty, the client temporarily mirrors AP-side Stump Temple Piece and Green Gem item counts into save flags so the in-game counters can display AP progress; this overlay is restored before level select screens so real in-game collectible visibility is preserved.
The `extra_counter_item_percentage` option controls how many extra counter items are added above the configured requirement.

Crystal Sanity and Junk Factory content will be added in later updates.
May add Deathlink as well, but similar to how it works in Celeste.
