# Savegame format

No save format has been established and no saves were modified.
No 578330 directory was present under the inspected Steam userdata account at research time.
The conventional candidate is Steam/userdata/<account>/578330/remote/savedgames/;
other installation libraries and user profiles have not been exhaustively searched.
Executable evidence includes LegoCitySaveGame and SaveGameData names; this does not identify serialized layouts.

Required experiment: on a dedicated test slot, quit cleanly and preserve baseline saves; collect one specific item,
quit cleanly again, and compare the entire slot and metadata. Repeat with another collectible and a restart.
Record hashes, file lengths, changing fields and checksums. Distinguish timestamps, currency and completion flags.
Only after integrity/checksum semantics are understood may a save writer be considered.
No backup/restore or Steam Cloud conflict detector is implemented because no save-writing feature exists yet.

## Slot 1 files located after first completed station save

The conventional Steam userdata path now contains feopts1, game1 and options1 with the suffix
.legocityundercoversavegamedata under remote/savedgames/slot1. A stable double-read backup of all three
was created in notes/save_backups/slot1_1794434637600223100 and verified with SHA-256.
The game1 file is 2,579,512 bytes; each options file is 8,288 bytes. The original files were not changed.
The backup does not establish the save layout, checksum semantics, Cloud synchronization or disk-format support.
backup_slot.py refuses existing destinations and aborts if files change during capture.
