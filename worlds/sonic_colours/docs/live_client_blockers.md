# PAL live repair following 6d939372

This is a partial P0 implementation, not a completed playable integration.
No AP server acknowledgement and no native effect write have been obtained.

## Fixed failure

The first live probe verified SNCP8P revision 0 against both executable text
hashes, then reproduced `invalid_pointer` in the old adapter. The save accessor
at 0x8015F940 returns the inline address `selected_save + 0x1C`. Its caller
0x8016C1D4 stores that address in a stack wrapper before passing the wrapper to
the bit helper. The helper's `lwz` unwraps that local variable. It does not
justify reading another guest pointer from the flags themselves.

Removing the incorrect dereference resolves the live chain. Observed manager
0x80B3FAC0, container 0x9310DDA0, selected index 1 and flag words 0x931273DC
are trace observations, not runtime constants. The chain is resolved afresh.
The user independently reported visible Slot 2; one observation does not prove
the visible-slot mapping for every internal index or establish save identity.

## Real observations

The JSON files named `live_pal_*.json` are bounded data reads with executable
revision hashes, timestamps, addresses, bytes and snapshots. They are excluded
from the distributable APWorld. Phase labels are operator reports, never
native scene evidence. The save-selection-pool capture happened during the
transition to the saved map and must not be treated as a verified menu trace.

- Forced Act 1 gameplay and its result: bits 150 and 151 unset.
- First save-selection capture after forced Act 2: both bits still unset.
- First saved map, user-selected visible Slot 2: both bits set.
- Regular return to title, reload Slot 2, map: both bits remain set.
- Regular Act 3 gameplay and result: bit 152 unset. Returning to the map and
  saving sets it; regular title-menu reload retains it.

Only the individually documented clear bits in
`data/native_read_validation.json` enter `persisted_clears`. Other mapped bits
remain `candidate_clears`. This is a limited persisted-read proof, not proof of
an intro completion event before saving. The adapter does not invent the two
bootstrap observations, a New Game flag, scene, mission or stable save identity.

## Executable proof path

```powershell
.venv/Scripts/python.exe worlds/sonic_colours/tools/probe_pal.py --phase operator_label --pool --output build/pal.json
.venv/Scripts/python.exe worlds/sonic_colours/tools/compare_pal_traces.py worlds/sonic_colours/docs/live_pal_act1.json worlds/sonic_colours/docs/live_pal_world_map_slot2.json
$env:AP_TEST_WORLDS='sonic_colours'
.venv/Scripts/python.exe -m pytest worlds/sonic_colours/test -q --disable-warnings
```

Use `--samples` (1..600) and `--interval` (0.1..10 seconds) for a finite trace.
The probe saves each completed sample; no global RAM scan is performed. `--pool`
adds only 28 header bytes and 40 flag bytes for each of the three code-derived
save structures. These headers are unresolved metadata, not identity tokens.
The production adapter tests replay actual recorded bytes; fabricated true
Snapshot flags remain supplemental state-machine tests.

## Remaining acceptance blockers

1. Independent native scene and actual mission acquisition, including the
   mandatory intro without a selected save. No current production field supplies
   title/New Game/result/gameplay/death/loading classification.
2. Two independent native New Game/freshness fields and a native completion
   observation for each intro act. Save C bits only become set at first save.
3. Stable save metadata identity that survives reconnect/reload but detects
   another save. A heap address, profile name or slot index is insufficient.
4. Live AP `LocationChecks` acknowledgement after safe seed/save binding.
5. Dynamic Stage/Player fields and a reviewed setter for one effect, followed
   by safe gameplay write/readback and HUD confirmation. All writers stay off.

For further native tracing, a useful code-derived debugger lead for regular
clears is the call at 0x8016E214: r30 is the receiver, r4/r5 are loaded from
receiver+0x44/+0x48 and passed to the clear handler. A breakpoint recording
those registers and their caller can help find a stable owner chain. This lead
is not a proven active-stage identifier, and it is not used by the client.
The running Dolphin process has no listening debugger port. The next requested
observation is PC/r13/r30/r4/r5 at that breakpoint after a regular clear, to
trace ownership and stage arguments without interpreting a stale heap address.
The user deferred this debugger observation for the night. Its expected result
remains an assumption and grants no native capability or verified evidence grade.
