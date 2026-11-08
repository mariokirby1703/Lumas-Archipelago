# PAL / NTSC-U disc verification

Verified against the locally supplied disc files on 2026-11-08. This is static
verification, not a completed Dolphin playthrough. PAL DATA/sys was not supplied;
its hp_r.elf was used. The NTSC-U main.dol was checked against its hp_r.elf.

## Result

PAL SECP69 and NTSC-U SECE69 build 525025 use the same memory layout. No region
address delta, alternate object IDs, alternate rules or alternate popup machine
code is needed. The connector and Windows MEM2 fallback both accept these IDs.
The fallback still requires the discovered MEM1 alias to match the currently
connected game's exact six-byte ID.

- All 40,136 ELF symbol entries have identical addresses, sizes and section IDs.
- All 13 nonempty allocated ELF sections have identical layouts, including BSS.
- All 6,015,664 bytes in executable ELF sections are identical.
- The only five differing allocated, file-backed bytes are the EU/NA build label
  and build time at 0x805F7409/0A and 0x805F7438/3A/3B.
- All ten NTSC-U DOL payload sections match their ELF counterparts. DOL section
  sizes include alignment padding, which is excluded from the payload comparison.
- All eleven popup/legacy/contraption patch original words match both regions.
- Both runtime patch ranges (0x80006048..0x80006514 and
  0x8062C100..0x8062C420, ends exclusive) contain zero bytes in both ELFs.
  The auxiliary range is inside the zero tail of ConsoleFont; the existing
  runtime still checks live contents and refuses an unknown nonzero range.

## Game resources

The audit compares all 22 files under PAL DATA/files with their NTSC-U peers,
and compares entries inside all 19 BIGF/BIG4 archives. The complete entry names
and difference counts are in [disc_audit.json](disc_audit.json).

In data.big, 29 entries are identical, two differ and nine are region-specific
localisation entries. All regular challenge level RPKs, including II worlds,
are byte-identical. game.cfg and all bootflow RPKs are identical. game.rpk has
71 differing bytes after RefPack decompression, in its SKU/language metadata
and associated size field. Hub levels/home.rpk has 150 differing decompressed
bytes; these have not been fully decoded. It is not claimed to be identical.

The other changed BIG entries have matching names and are .tga, .wnk and .lef
resources. Audio, materials and thumbnail BIG archives and movies.big match.
The separate sound/Create.pck files differ in size (PAL exactly 512 MiB,
NTSC-U 1,036,026,844 bytes); completeness of the supplied PAL sound file is
unverified. No AP object mapping or challenge requirement has been changed
based only on these resource differences.

The RAM-map Total Sparks metadata was stale: the existing implementation writes
received AP Sparks to the in-game display when the Spark requirement is positive.
The metadata now describes that existing behavior.

## Reproduce

From the repository root, with local disc files under worlds/create/notes:

```powershell
python tools/create/disc_audit.py --output worlds/create/docs/disc_audit.json
.venv/Scripts/python.exe -m pytest worlds/create/test -q --disable-warnings
```

The audit requires only the standard library and outputs metadata, hashes and
resource names, without extracting game assets. It fails if the compared symbols,
layouts, executable bytes, known five-byte difference set, patch originals,
patch ranges or NTSC-U DOL payloads no longer match the verified build.

Validation: 188 tests passed, including 5,707 subtests. New regression cases cover
both connector region acceptance and the Windows MEM2 region gate, plus refusal
of unsupported and incomplete IDs. Existing tests cover memory sync, popup image
construction, runtime guards, progression and generation.

## Remaining in-game verification

For each region, freshly boot Dolphin without a save state or old Gecko popup
helper. Use a fresh Save Slot 3 and the same generated AP seed.

1. Connect the client and verify the slot guard arms.
2. Receive World Access and Objects; confirm palette filtering and placement.
3. Complete a normal challenge and verify each Spark check once.
4. Complete the Hub tutorial and a normal Create Chain; verify checks and flow.
5. Run /createpopup 13; verify image/name, normal close, restored input and a
   changing heartbeat in /createpopupstatus. Check real item receipt popups too.
6. Verify AP Spark display, goal completion, reconnect and a world transition.
7. On Windows, confirm Object MEM2 sync also works when the fallback is selected.

No in-game NTSC-U result is asserted by this audit.
