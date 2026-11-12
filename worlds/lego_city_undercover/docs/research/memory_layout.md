# Memory layout

No live collectible bit indices, save pointers or safe callable interfaces are confirmed.
A live main-menu read validated the ability object pointer and symbol-table references below;
state-byte semantics still require a controlled gameplay transition.
The preferred PE image base is not a runtime address: ASLR requires module-base resolution per process.
The bridge diagnoses processes with Toolhelp snapshots and QueryFullProcessImageNameW, validates the full executable
hash, enumerates the main module and can read its 64-byte DOS header using ReadProcessMemory.
It requests PROCESS_QUERY_LIMITED_INFORMATION and PROCESS_VM_READ only.
Unknown executable hashes do not proceed to a module memory read. No write API exists in this bridge.

The observed absent-process path was tested on Windows. A running-game header read and main-menu ability snapshot succeeded outside the sandbox.
The normal sandbox denied process access. This does not read Studs or Gold Bricks.

Next experiment: locate script-action registration records using the string/RTTI evidence, disassemble registration
and handler cross-references, establish object lifetimes and then compare state before/after one collectible.
Never derive an unlock pointer by treating a string file offset as a function address.

## Static method candidates

Reproduced by `.venv/Scripts/python.exe worlds/lego_city_undercover/tools/action_xrefs.py` using Capstone.
The tool finds a RIP-relative LEA/RET returning each action name, then pointer-table references to that getter.
The method pointer three slots after the getter is a candidate based on repeated table layout and disassembly.
These are RVAs for the exact executable hash in engine_analysis.md; none has been invoked or live validated.

| Action | Name getter RVA | Candidate method RVA |
|---|---|---|
| UnlockAbility | 0x18210 | 0x90550 |
| PlayerGiveStuds | 0x17990 | 0x107ec0 |
| CommitCollectables | 0x176f0 | 0x105ff0 |
| UI_SetMissionMessage | 0x18090 | 0x10d0b0 |
| CityObjective_IsComplete | 0xedd90 | 0xecdb0, 0xecd40 |
| CityObjective_SetComplete | 0xedde0 | 0xed310, 0xed2b0 |

The two objective method candidates may represent overloads; parameter semantics require further analysis.
UnlockAbility candidate disassembly at RVA 0x90550 reads script context fields at +0x50/+0x59,
calls an argument resolver, and searches 0x33 32-bit values at RVA 0x17f84d0.
It reads a global pointer at RVA 0x17ebd48 and conditionally stores one byte at pointer+index+0x10b,
then dispatches an event. These observations are static instruction evidence, not a validated unlock structure.
The pending byte alone is not sufficient justification for an external memory write.
PlayerGiveStuds likewise consumes a script context, not a simple integer-only function signature.
Full disassembly snippets remain in ignored notes/analysis/action_xrefs.json.

## Live main-menu evidence

The running installed game had the same full executable hash as the supplied copy.
Toolhelp resolved its ASLR module base and ReadProcessMemory successfully read its header,
the ability manager pointer, its 51-entry symbol hash array and two 51-byte candidate state arrays.
Both state arrays contained zero in the main menu. This validates address accessibility and table identity,
not yet the interpretation as available/pending abilities during play.

All 51 runtime hash values match uppercase FNV-1 (multiply by 0x1000193, then XOR each byte, seed 0x811c9dc5).
The separate archive hash must not be used for these symbols. Reproduce name associations using
tools/map_ability_hashes.py and the ignored notes/analysis/live_main_menu.json snapshot.
Examples: GrappleGun index 0, Scanner 8, Jetpack 18, FireAxe 19, SuperStrength 48, Act2 49.
District-related symbols share this table; it is not a list exclusively of character abilities.
bridge/research_profile.py validates all hashes before interpreting the experimental read by name.

## Objective table candidate

Static disassembly of the IsComplete candidate calls RVA 0xf0150 for string-name queries.
This routine reads a manager pointer at RVA 0x17eca28; a container at manager+0x950 contains
a record pointer at +0, signed 16-bit count at +0xa, and 12-byte records.
The lookup at RVA 0xeb950 compares each record's first 32-bit value to a hashed name;
RVA 0xebad0 returns the signed 16-bit record count.
RVA 0xf0150 then reads a signed 16-bit bit index at record+4 and tests that bit in
the data pointed to by the object pointed to at manager+0x978.
The setter candidate also updates a second bitset through manager+0x988 and dispatches an event.
This makes an isolated bit write inappropriate.

bridge/objective_reader.py implements a bounded, read-only experimental parser and checks container pointers again
after its snapshot. Synthetic tests cover bit decoding and invalid inputs. No live record or completion transition
has verified this objective layout; the output is not yet suitable for automatic AP checks.

## First controllable-scene read

A later live snapshot successfully read 1,059 objective records; every hash matched a scanner resource instance name.
There are 1,058 unique hashes. SwapBrown occurs twice in both the resource and live table, with bit indices 1058
and 1055. The reader excludes both ambiguous records instead of choosing one. The remaining 1,057 candidate
completion bits were zero at the start. SF_Docks and DisguiseBooth were the only positive ability-query results.
The user reported 10 Studs and zero Gold Bricks; those counters have not been read from memory.
This validates the initial objective table layout, not a completed-objective transition or save persistence.
