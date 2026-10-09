# PAL memory evidence and first live probe

All supplied notes were inventoried and structured data parsed. Matching copies
of the master spec and shared static research are byte-identical. See
`research_audit.json` and `tools/audit_research.py` for hashes and reproducible
checks against the dev-only ELF. The supplied old scripts contain `/mnt/data`
paths and depend on absent originals, so they cannot be run unchanged here.

## New static discovery

The ELF32 PowerPC wrapper contains original text sections. At `0x80004294`,
`lis r13,0x808f` followed by `ori r13,r13,0x9520` sets `r13=0x808F9520`.
`0x80160C10` reads `lwz r3,-0x5EF8(r13)`. The resulting candidate manager global
is **0x808F3628**. This is code-derived, not guessed from a heap snapshot; it
still needs confirmation in the running game and after a restart.

Candidate chain:

```text
manager       = read_u32(0x808F3628)
container     = read_u32(manager + 0x30)
index         = read_u8(container)
selected_save = container + 8 + index * 0x19608
flags         = selected_save + 0x1C
word          = flags + 0x10 + 4 * (bit // 32)
mask          = 1 << (bit % 32)
```

The flags are inline. The `lwz` in the bit helper unwraps the caller's stack
wrapper (see `0x8016C1D4`), not a pointer stored at `selected_save+0x1C`.
The previous client incorrectly added this dereference. A live PAL Act 1 read
now resolves manager `0x80B3FAC0`, container `0x9310DDA0`, internal index 1,
and C bank `0x931273DC`; these heap addresses are observations, never constants.
External memory addresses are Wii guest
addresses, not Windows process addresses. `index=0` has not been proven to mean
a visible UI slot. The resolver accepts internal indices 0..2 as candidates only;
any visible slot is permitted after identity proof. The game forces Acts 1/2 before
first save selection. New Game/scene/save identity fields are still unresolved.
Memory is bounded to MEM1 0x80000000..0x817FFFFF and MEM2
0x90000000..0x93FFFFFF, with pointer alignment and end bounds checked.

Progress groups A/B/C use bases (30,210), (90,231), (150,252). The 66 actual
stage entries have unique bit indices in each bank. C is written by the clear
handler `0x8016C1B4` via `0x8015EF7C`, but persisted clear semantics and loading
behavior need observation. `0x8016C2FC` checks all 21 Game Land C bits, then bit 7.
Event values 110/140/170/180 are event IDs, not gate costs. Special bits 273..302
and their translator remain unmapped.

## Evidence that must not become a writer

`0x90B25F1C`, `0x90B25F20`, `0x90B25F30` and `0x90B25F70` are transient heap
snapshot fields for lives, rings, held Wisp and temporary stage mask. Their
absolute addresses are not used by runtime writes. The mask extraction is
`(word >> 16) & 0x1F`, not the low five bits. Neither checkpoints nor death survival
prove permanent save persistence. `0x80AED9B0` later contains a pointer and is
rejected as a global counter. ORC template offsets are file offsets, never RAM.

`0x80055E98` originally loads `lwz r6,0x18(r30)`; `0x8027E744` loads
`lbz r0,0x120(r31)`; `0x800381C4` loads `lwz r0,0x10(r3)`. None proves a native
setter. Life decrement hooks `0x8001BE60`/`0x8024CBB0` do not identify a kill routine.
Capsule subtype names remain hypotheses. Full executable text hashes were derived
from the ELF; original main.dol is absent, so its recorded whole-file hash is
provenance from the supplied spec, not independently recomputed.

## Smallest next runtime observation

With the exact PAL executable running, back up the save first. Run:

```powershell
.venv/Scripts/python.exe worlds/sonic_colours/tools/probe_pal.py --output build/sonic-pal-probe.json
```

Capture the small report at the title/New Game screen, forced Act 1/2 results,
then first vanilla save selection and after choosing any available slot. Confirm
pointer lifetime, internal-index changes and C candidate bits across restart.
The probe only reads; it neither binds a seed nor sends AP checks or writes memory.
It cannot identify a New Game transition from the pointer chain alone.

On a disposable new playthrough, observe Act 1 C bit 150, expected word at
`flags+0x20`, mask `0x00400000`; Act 2 bit 151 uses `0x00800000` in that word.
Resolve the base again after save/reload. Record actual native scene transitions
and freshness fields before any write experiment. No such live write is verified.

The new rework notes and `offline_re` tables supply no additional native addresses.
`data/native_evidence.json` and `client/evidence.py` explicitly classify field
proof. Unknown New Game, save identity, scene, stats parent and capsule opening
fields are not replaced with guesses.
