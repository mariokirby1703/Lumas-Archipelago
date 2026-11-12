# Engine analysis

Confirmed by static inspection of the supplied executable:

- AMD64 PE32+, preferred image base 0x140000000, eight sections.
- File SHA-256: `624fed07274bbd105d1d571ecb97a290df6f6f0aff76898c516890da6d136f76`.
- ASCII strings include script action names and MSVC RTTI class names for save and collectible systems.
- Local gameversion data identifies DX11, BuildRecordId 15609011, TTBuilder 1.30.45,
  build date 2017-05-16, transaction 10447578. This is data-file identity, not a supported memory profile.

Evidence offsets below are decimal file offsets, not live addresses:

| Evidence | Offset |
|---|---:|
| GivePlayerStuds | 12679864 |
| UnlockDisguise | 13169384 |
| LegoSaveGame | 14210952 |
| SaveGameData | 14475520 |
| MSVC RTTI LegoCitySaveGame | 16748472 |
| MSVC RTTI ScannableCollectableManager | 16919296 |

Reproduce via tools/inspect_game.py; complete strings remain in notes/analysis/LEGOLCUR_DX11.exe.strings.json.
No calling convention, game-thread scheduling, object ownership or function parameter layout is established.
No allocation manager, safe HUD call, save checksum or memory write has been verified.
See memory_layout.md for statically identified action-method candidates and live read evidence.

Archive format is CC4/0TAD, big-endian index version 2, kind -11, with 64-bit entry offsets.
The outer eight-byte locator is little-endian and uses an inverted page offset for these files.
All 76,584 indexed payload spans passed archive bounds checks. 76,582 have CRC-matched names;
one entry each in GAME1 and GAME4 remains unnamed. Never assign fallback names to those entries.
The custom name hash normalizes uppercase backslashes and uses multiplier 0x199933.

ZIPX payload chunks in the selected research files decode with RC4 using their packed chunk size as a
four-byte little-endian key; size-equal chunks require no decompression. The level table crosses multiple chunks.
The reader also supports raw deflate chunks; this branch has synthetic tests, not independent QuickBMS comparison.
No original archive was modified. QuickBMS was not installed; its script was read as a format reference:
[LCU extractor](https://github.com/linterniGamer/Tt-Games-quickbms-scripts/blob/main/files/ttgames_LCU.bms).
