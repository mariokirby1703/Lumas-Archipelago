# Live Check Monitor

Version 8 artifact: `build/lego_city_undercover/LCUCheckMonitor_v8.exe` fixes
pending-only character/class grants. The user's robber unlock log showed model
228 Robber and co-op alternative 709 Chase_P2_Robber with found=false, owned=0,
pending_grant=true. The previous detector only handled found/owned transitions.
Pending acquisition now emits an unlock event with raw model data; its subsequent
found/owned commit is suppressed as a duplicate. It does not turn these companion
events into independent AP locations. Replayed against the supplied before/after
annotation snapshots, both pending grants are detected. 59 tests and EXE window
smoke test passed. New connection still deliberately does not replay old unlocks.

Version 6 artifact: `build/lego_city_undercover/LCUCheckMonitor_v6.exe` shows attached
item definition names beside the context history and logs changes, including the
initial list, in JSONL/clipboard exports. Both UI and records explicitly label hand
possession unverified. PDA/tools may be listed while put away; generic carried
world props may not appear at all. An empty list must not mean empty hands.
Static research confirms Character_GetItemOut (typed method RVA 0x112ab0) calls
item operations to bring a requested item out; it is not a passive held-item query.
No engine function is invoked. The display uses the existing bounded actor reader.
57 tests, window smoke test and a live reader sample passed.

Version 4 artifact: `build/lego_city_undercover/LCUCheckMonitor_v4.exe` adds a
separate right-hand context history and current action label. Context is sampled
approximately every 100 ms between slower acquisition snapshots. Only changes
are appended, including return to a previous context. Context changes are included
in JSONL and clipboard exports with index, name, previous state, actor and time;
they are not pickups/checks. Very short actions can still be missed, particularly
while a full snapshot is being read. Reconnecting starts a fresh context history
baseline. 55 tests and the executable window smoke test passed.

Version 3 artifact: `build/lego_city_undercover/LCUCheckMonitor_v3.exe` adds logged
area and story section separators, before collection events in the same sample.
Native tile changes within one area are ignored. Re-entry prints the area again;
unknown readings preserve the last known identity without guessing a new area.
The five user-correlated area prefixes have friendly names; others display their
internal area identifier. Story separators use the native campaign cursor for all
four acts, not yet an independent Special Assignment ID or localized title. Stage
changes within a mission do not create a new heading; transient mission zero is
ignored. Consequently standalone entry/replay with an unchanged campaign cursor
is not yet independently separated. These headings are not location checks.
Validation: 54 tests, a live snapshot and EXE window smoke test passed.

Version 2 artifact: `build/lego_city_undercover/LCUCheckMonitor_v2.exe`.
`Log kopieren` exports structured JSON for all events captured by this window,
including native identities, before/after values, pickup byte offsets/masks,
payload address and native tile/player position when available. The tile describes
the player's sampled location, not guaranteed collectible ownership by district.
This also works after disconnecting. Existing JSONL logs are still written.

The editable mission annotation selector and `Diagnose markieren` request a fresh
read on the worker thread. They store a manually reported event plus current and
previous annotated snapshots (initially the connection baseline), and known story
values. Use `Level betreten` once loaded, then mark an individual quarter or Hero
milestone immediately after observing it. These annotations do not recognize or
confirm shield/hero/completion memory flags and never create AP checks. Clipboard
exports clearly retain `automatic_detection: false` for them.

Version 2 validation: 52 tests passed, executable window smoke test exit 0.

Start `build/lego_city_undercover/LCUCheckMonitor_v14.exe`, load a game save and press
**Mit Spiel verbinden**. The first stable snapshot becomes the baseline: old
collections are not announced. New city flags, Super Brick bits, character/vehicle
discoveries, ownership changes and ability unlocks appear with timestamps. JSONL
event logs are saved in `monitor_logs` beside the EXE. Use a writable directory.

This is a standalone Windows x64 executable with its Python/Tcl/Tk runtime included.
It does not require a separate Python installation. It uses only query/read process
permissions and verifies the supported executable SHA-256. If access is denied,
run monitor and game with matching privileges. Connect after loading the save;
disconnect before switching save slots and reconnect afterwards.

This is an experimental observation tool, not an AP client. It sends no checks,
grants no items, and implements no locks. A changed native flag is shown as a flag,
not asserted to be a finalized AP location. Character/vehicle discoveries are
explicit companion events: they are not extra checks for a booth or Super Build.
Gold Brick totals are diagnostic only and never generate a location event.
Known objective names use generated factual scanner metadata. Only six observed
Super Brick mappings currently have names; other bits say not yet assigned. No
general bit-to-source formula is claimed. Currency deltas alone do not create checks.

The monitor samples once per second. Very short transient actions are not covered;
it monitors persistent acquisition/completion changes. Pending-to-owned autosave
commit is not treated as another discovery. Reconnect deliberately takes a fresh
baseline, so offline pickups are not replayed as new events. Save/seed binding,
full scene-transition coverage, native district display and complete collectible
mapping remain future work.

Build: install PyInstaller in the repo virtualenv, then execute
`tools/build_live_monitor.ps1`. Build input is the bridge Python modules and two
explicit JSON metadata files; no game archives, saves or raw scripts are bundled.
Generate label metadata with `tools/build_monitor_labels.py` when research changes.
The native experimental DLL is not part of this executable.

v14 replaces actor-scene-only pickup observation with bounded loaded-scene
enumeration and per-connection identity memory. It records newly learned pickup
identities, source ambiguity and individual native object flag changes. Context
transitions include positions for the verified actor transform. The clipboard
log includes these observations even when the object disappears before collection
is detected. Coverage and cached identity counts are displayed below the stats.
Reconnecting clears this cache; disconnect before changing save slots. It does
not make unsupported red bricks, mission shields, hand objects, area sensors or
native grants/locks fully implemented. See research/automatic_observer_coverage.md.
84 tests pass, frozen window smoke and live snapshot both exit successfully.

The right-hand diagnosis pane has Objects, Scan Auras and History tabs. Objects
shows the selected GizSwitch candidate and all supported loaded GizSwitch/Techno
instances, sorted by distance. Nearby does not mean underfoot or usable. A native
marker prediction identifies class/tool variants, including locked variants, from
the exact marker branch ordering and observed class/ability grants. It does not
assert actual rendered visibility or a complete eligibility decision.

Scan Auras reads the native player's registered AudioScan, CriminalScan and
DetectiveMode markers independently of action context. This reader is experimental:
an empty registry is not proof that no aura exists. Inside/outside, actual scan
activity and full lock state still need in-game validation. Other systems/layouts
remain unknown. New diagnostic records `scene_fields_change`, `scan_markers_change`
and `interaction_target_change` are included in Log kopieren and JSONL, without
becoming pickup/AP events. Losing a reader clears its current presentation.

Validation covers event handling, scene resolution, cycles, scene changes,
separate scan types, unknown states and marker branch precedence. Current prison
source readers have read 19 objects and an empty scan registry live; interpreted
nonempty aura observations require a targeted game test. See research/interaction_fields.md
for native evidence and the limitations of predicted locks.

v11 defaults to immediate proximity: horizontal distance <=0.75 and absolute
height difference <=0.35 source units. These are conservative display filters,
not native interaction boundaries. The optional "Gesamte Szene anzeigen (Diagnose)"
checkbox restores all loaded objects. Full scene data remains in copied logs.
Selected native targets outside this filter are not presented as an immediate
field. Regression tests include a safe one floor below the player. User's general
field was independently read as #cg_592_KEYPAD_USE_SW at distance 0.05118,
flags 0x100000, selection result 3. User reports all disguises can use this field;
this observation is not generalized to every keypad or object with that flag.

v12 fixes scan-type decoding after the first nonempty in-game marker observation:
the definition's first word is a string header, not the type hash. The reader now
uses its type-name string (verified DetectiveMode / SC_DetScan) and preserves it in
logs. 74 tests passed and the frozen EXE window smoke test exited successfully.

In-game validation sequence for v10:
1. Connect while standing at the second closed crowbar door. Confirm its object
   name, nearest distance and Robber_Crowbar prediction. Record a diagnostic note.
2. Step away, then return; compare selection/proximity changes. Change outfit while
   retaining the same unlocked classes: class-unlock marker prediction should not
   be mistaken for current-outfit eligibility. Capture the native selection result.
3. Stand outside a visible detective aura; record a note, step into it without
   starting the scan, record another note, then scan and step out. Copy the log.
4. Repeat for criminal/person and conversation scan when available, plus a visible
   locked class field. Compare native marker observations against the game display.
Do not require replaying the intro or recollecting persistent rewards for these tests.

v10 validation on 2026-11-13: 73 unit tests passed. The frozen EXE completed
--ui-smoke and --sample-output with exit code 0. Its live read reported 19 scene
objects, an empty scan registry, and the second door's native selection result 3.
Crowbar, detective, locked construction and locked fireman marker predictions
were present. Nonempty scan markers and the relation to aura entry remain to test.
