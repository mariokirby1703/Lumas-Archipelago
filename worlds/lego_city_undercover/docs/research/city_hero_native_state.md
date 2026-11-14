# LEGO City Hero: native current-mission state

2026-11-13, pinned research EXE SHA-256
624fed07274bbd105d1d571ecb97a290df6f6f0aff76898c516890da6d136f76.

The decisive code is RVA 0xa12198..0xa122ca. It calls threshold getter 0x7ecbe0,
accumulates the two player stud sources (component +0x320) in global
0x1c7e6e0, compares the accumulated uint64 with the level target at 0xa12257,
and upon reaching the target sets uint32 0x1c7e6e8 and float 0x1c7e6d8 to 1.
It then dispatches the completion notification through 0x8e76d0/0x9d6800.
The animation float is not used by the reader as completion evidence.

Getter 0x7ecbe0 selects slot 0/1 of a level threshold. Mode global 0x1c7eb60
equal to 1 reads scene level +0x18 metadata +0x160. The other path uses the
signed level index at that metadata +0xab, the descriptor table at global
0x1c7d430 (count 0x1c7d438), stride 0x350, threshold +0x190. Caller selection
uses global 0x1c7e61c, overridden to slot zero when 0x1c7e608 is nonzero.

The read-only live validation found level index 4, 90,000 accumulated studs,
90,000 target and completion latch 1. The player's scene had advanced to
Mine_Freefall, mapping to mission mine. Against the existing connected seed,
the detector selected exactly mine: LEGO City Hero, location 1866425495.
The validation sent no server messages and wrote no game memory.

The client now logs and reconciles this result through the existing mission key,
so no regeneration is needed for seeds already including City Hero locations.
The latch, valid mission identity and nonzero reached target must all agree.
Counter/latch and player scene are checked again before accepting a snapshot.
Other missions use the same getter but have not yet received isolated live tests.
Persistent backfill of every past mission remains separate work: this reader
only establishes completion in the currently loaded mission.

Excluded leads: +0x4c bit 1 in manager 0x11754b0 belongs to HUD animation state;
stats +0x3354 is initialized to a fixed 100,000, unlike the mine target 90,000.
Neither is used as the City Hero trigger.
