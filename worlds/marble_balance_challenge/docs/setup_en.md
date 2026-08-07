# Marbles! Balance Challenge Setup Guide

## Required software

- Archipelago built from this repository.
- Dolphin with a PAL `Marbles! Balance Challenge` / RK6P18 copy.
- An external client that can connect to Archipelago and read/write Dolphin RAM.

## Before playing

Use Save Slot 3 for AP testing and play. The RAM notes and slot data assume save slot index `2`.

Generate a seed from the Archipelago launcher or command line using a player YAML for `Marbles! Balance Challenge`.
The generator writes an `.apmbc` file containing slot data, location metadata, item placements, and PAL addresses for
the client.

Bonus worlds and Free Mode checks are always enabled in V1. Tutorial checks and Wii Balance Board checks are optional
and default off. Crystal Sanity is intentionally left out of V1.

## Safety notes

The client must not write AP received items to Green Gem, Stump Temple Piece, Trophy, or other check flags. Those flags
are location detection sources. Writing them can create false checks or remove collectibles from levels.

Submarine and Rocket Ship flags should not be written alone. When they are exposed in RAM, the matching safe target
world levels must also be unlocked so the game cannot enter an empty/crashy world state. If Split Vehicle World Access
is disabled, Submarine and Rocket Ship are not AP items and world access items alone control W5/W6 logic.

Wii Balance Board checks are optional and should be detected through stage identity plus a goal reached latch, not
through vanilla completion flags.
