# Sonic Colours (Wii) Setup Guide

## Required Software

- [Archipelago 0.6.7](https://github.com/ArchipelagoMW/Archipelago/releases/latest) or newer
- [Dolphin Emulator](https://dolphin-emu.org/download/) (64-bit)
- An unmodified, uncompressed PAL Sonic Colours Wii ISO, game ID `SNCP8P`, revision 0
- The [Sonic Colours `.apworld` file](https://github.com/mariokirby1703/Lumas-Archipelago/releases)
- [Wiimms ISO Tools](https://wit.wiimm.de/): installed automatically when needed on Windows; install it separately on other platforms

Other game regions and revisions are not supported. Allow approximately three times the ISO's size plus 2 GiB of free disk space.

## Installing the APWorld

1. Install Archipelago and download `sonic_colours.apworld`.
2. Double-click the `.apworld` file to install it.
3. Restart the Archipelago Launcher and check that the Sonic Colours Client appears.
4. If Archipelago asks to install missing requirements, allow it. The client needs Dolphin Memory Engine to connect to Dolphin.

## Creating a YAML and Generating a Game

Create a Sonic Colours player YAML using the Archipelago Launcher and set your player name and options. Place the YAML in your Archipelago `Players` folder for local generation.

Generate the multiworld through Archipelago. The output contains a player-specific `.apsoniccolours` patch. Keep it for your seed.

## How to Play

1. Open your `.apsoniccolours` patch using **Open Patch** in the Archipelago Launcher or the Sonic Colours Client.
2. When prompted, select your Dolphin executable and your original PAL revision 0 ISO. The installer creates a separate patched ISO; your original stays unchanged.
3. Wait for the patching and verification to finish. Dolphin can start the patched ISO automatically; if automatic startup is disabled or skipped, open the patched ISO in Dolphin yourself.
4. Connect the client to your Archipelago room using its full address and port, your player name and, if required, the room password. A hosted-room patch may already contain the address and player name.
5. Connect **before starting New Game**, so the client can detect checks during the opening Acts. Choose a free save slot when the game prompts you.
6. Wait for the client to connect to Dolphin and verify the game, then play normally. Keep using the same patch, patched ISO and save for the seed.

No manual Gecko codes or Riivolution setup is required. Keep the generated ISO and its accompanying `.iso.sonic.json` file; the generated ISO contains game data and should not be redistributed.
