# Marbles! Balance Challenge

Marbles! Balance Challenge is the PAL name for Marble Saga: Kororinpa. This Archipelago world targets the PAL
RK6P18 release through an external Dolphin client.

The world treats Archipelago inventory as authoritative. The client should only write safe unlock/display RAM and
must not write collectible or trophy flags when receiving AP items.

## What is randomized?

By default, the world creates campaign goal checks and the A-C bonus worlds, while leaving Tutorial, Wii Balance
Board, Green Gem, Stump Temple Piece, Anthony, and Trophy checks off. Marbles and Figure Roller heads are always
randomized. Recipes and Junk Factory access are controlled together by one option. Junk inventory items are always
filler items, and traps can replace filler based on the Trap Chance option.

Important AP-side counter items:

- `Green Gem`
- `Stump Temple Piece`

These are logic items only. They should not write the game's Green Gem or Stump Temple Piece collectible flags.
The `extra_counter_item_percentage` option controls how many extra copies are added above the configured requirement
for both counters. The default is `25`, meaning a requirement of `60` creates `75` counter items.

## Goal

The default goal is `Stump Temple 10 Normal Goal`. A Hard goal can be selected, in which case Hard Mode access is
controlled by the selected Hard Mode Unlock option. If the Hard goal is selected, Hard difficulty is always included
even if the difficulty option would otherwise exclude it.

## Client notes

The generated `.apmbc` output and slot data include the PAL RAM addresses currently documented in the notes folder.
The client should use Save Slot 3 safety checks and the current-stage identity stack from the notes.
