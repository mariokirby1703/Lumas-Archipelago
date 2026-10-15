# Native seed patch migration — validation record

Updated 2026-10-14. This is an implementation and verification record, not a declaration that every gameplay regression has passed.

## Installation architecture

`patch.py` registers the official Archipelago player container `.apsoniccolours` and the legacy `.apsonic` JSON reader. New output contains only `archipelago.json` and `seed.json`. Game, player, seed, revision, schema and native/resource component fingerprints are validated before installation. Legacy migration requires an explicit player slot and creates a separate file.

`client/iso_patch.py` selects and remembers the user's original ISO, verifies its DATA partition with WIT, extracts into a private temporary directory, validates the original DOL and CPK hashes, performs one combined HUD/music resource build, patches the DOL, rebuilds the encrypted Wii partition and verifies the output. It rechecks the original ISO hash before finalization. Existing output is reused only with matching metadata and a verified complete output hash. Other existing destinations are refused. Cancellation and failure do not replace the original or publish a partial build.

Windows can obtain the pinned official WIT 3.05a bundle automatically; other platforms require WIT on PATH or an explicit path. WIT remains a separately licensed tool. Original game resources, generated CPKs and generated ISOs are excluded from the APWorld and seed containers.

`client/native_dol.py` translates all 22 existing Gecko C2 payloads into ordinary mapped DOL code and retains the direct writes. The C2 headers and Dolphin codehandler are unnecessary. Including the new area-map refresh hook, the executable payload is 3,608 bytes, within a 6,144-byte initialized text section at `0x80001800`. The section is checked against original sections and BSS. Each hook uses a checked aligned PowerPC branch, and each C2 payload returns to its original hook plus four bytes. The complete registry has 174 patch sites, including the bounded HUD renderer and audited publisher/Rocket padding sites.

The original whole-DOL checksum is mandatory before any instruction replacement. Patch ranges must not overlap. The `SCAPNAT1` handshake at `0x80002FC0` records ABI, native code digest and seed identity. Runtime revision verification checks native hook sites and retains normalized original PAL text verification. Generated-ISO clients reject a missing or mismatched native seed marker. Manual legacy Gecko/Riivolution overlays must be disabled for this ISO.

`tools/build_hud_overlay.py` builds gameplay, world map, area map and Game Land resources together with optional seed music. The targeted tool allowlist in `build_apworld.py` includes the required local builders and excludes research captures and original assets. Package import tests exercise the builders from a ZIP APWorld.

## Validation evidence

| Check | Result |
| --- | --- |
| Original and rebuilt Wii DATA partition verification | Implemented; rebuilt test ISO passed WIT verification |
| Original ISO preserved | Build rehash passed |
| Native boot without manual Riivolution/AP Gecko | User started generated test ISO; native handshake and normalized PAL revision passed live |
| Seed music in generated resources | User heard custom music; live bank matched SonicTest0 |
| Real AP transport, two connected players | Actual local MultiServer, Luma and HUDPeer; controlled test rewards |
| Physical Red Rings 1 and 3, Act 1 clear and ranks | Checks acknowledged by real server |
| Received/Found/Sent gameplay HUD | User visually confirmed working |
| Second mandatory Act and save binding | Completed; client reached `bound seed/save resumed` on world map |
| World map HUD | User visually confirmed working |
| Area map HUD | User visually confirmed working |
| Game Land HUD | Further live confirmation pending |
| Physical 1-Up with generated native ISO | Act 4 native latch changed from 0 to 8; location 847020003 acknowledged by actual server separately from Red Ring 5 (847001101) |
| Every Wisp, movement lock, native bonus and reconnect | Full live regression matrix pending |

The integration server uses controlled rewards, not a claim of successful restrictive-fill generation for every option combination. Runtime ACKs establish publisher execution; visual appearance is recorded separately. Build receipts deliberately retain `boot_verified: false` and `live_verified: false`: an offline installer cannot certify a user's later Dolphin session.

The full Sonic suite completed with **17,936 passed and 38 failed**. The same 38 failures were reproduced on unchanged baseline commit `9c6b601192304e9ea10adc549c4ac17401afb74d`: 33 option/count/logic/state/static expectations and five transport fixtures. They have not been hidden or relaxed. New migration, container, native branch/handshake, cache and package tests pass. Local detailed reports are under `build/patch_reference/`; that directory contains private build artifacts and is not release content.

## Outstanding release verification

The complete ISO build was repeated successfully using ZIP-imported modules from the release APWorld, the original ISO and WIT, with rebuilt DATA partition verification and original-preservation rehash. The 18 targeted migration/package tests passed.

During the live run, Progressive Crouch level 2, Homing Attack and Stomp were granted through the actual isolated AP server to permit further progression. The user recalls collecting a white capsule before White Boost Wisp ownership; this is an unconfirmed observation requiring a separate no-White-ownership test of capsule pickup and enemy Boost grants. The current run already owns White Boost Wisp and cannot establish that earlier denial behavior.

The physical Act 4 1-Up awarded Homing Attack in the controlled reward table; the subsequent Red Ring 5 awarded an AP 1-Up item. Both checks are independently acknowledged. The user reported delayed HUD notifications. The server log showed approximately 2.7 seconds between the first check's server handling and client message processing, so notification latency remains an open performance issue; it cannot be attributed solely to native rendering. Paused Dolphin also prevents game-thread mailbox acknowledgements.

After Act 4, the user reported the Act 5 path appearing only after area-map reload. A read-only live capture confirmed nodes 1–4 at status 4 (cleared), node 5 at status 2 (available), and nodes 6–7 at status 1 (locked). This establishes stale visual/path initialization rather than missing Act 4 completion or missing Act 5 permission. A native area-map refresh is now implemented at update site `0x8026ADE4`: exact waypoint changes trigger native adjacency calculation (`0x802693AC`) and existing path-buffer rebuild (`0x80269F90` / `0x80267880`). The new generated ISO passed WIT verification and the migration tests; the behavior still requires a fresh live test. The existing Grand World Map refresh handles a separate actor.

Complete the live rows above, including at least 30 seconds of stable HUD display, concurrent native bonuses, Act and map changes, reconnect without receipt replay, all Wisp subabilities, movement denial and subsequent unlock, physical 1-Up sanity and Game Land counters. Investigate the baseline suite failures before describing the entire branch as regression-clean. The native workflow exists; complete independent release certification is still pending these checks. The current controlled test has Boost Lock disabled and has awarded White Boost Wisp; unrestricted Boost in that configuration is expected and does not verify denial before ownership.

The first live refresh revision restored navigation but not path visibility: the PAL adjacency helper only clears `+0x690` flags and does not re-enable previously hidden paths. Revision 3 restores the original resource-existence predicate from the native initializer before endpoint filtering and vertex rebuilding. On 2026-10-15 the user confirmed the Act-5 path is now visible. The Act itself still appears black despite being navigable; the user explicitly deferred that appearance fix until after testing Act-5 completion. The matching revision-3 client reports `bound seed/save resumed` with 24 received items.

After completing Act 5 with revision 3, the user also confirmed the path to Act 6 is correct. This validates the completion-driven path refresh beyond initial map entry. The newly available Act's black waypoint appearance remains a deferred UI issue.

Game Land 1-1: the user confirmed Ring Loss Trap removed rings and its message appeared in the HUD. Its initial light-blue colour was caused by MultiServer `!getitem` sending flags=0. The ticker now infers classification only for known own-game cheat receipts (location=-1, own sender, absent flags), preserving ordinary server flags and foreign receipts. All 12 ticker tests passed, including this distinction. Visual red-colour confirmation after the client update is pending.

The follow-up live test confirmed the Trap name is red after the client update. With Assist Change unlocked and the assist selected, Rings, Ring Loss Trap, 1-Up and Full Boost Refill affected normal Sonic's inventory rather than the assist's separate counters. The user explicitly requested retaining this behavior. These AP consumables must continue targeting normal Sonic while assist is active; this is not an assist-counter bug to fix.

## Capsule detection rewrite (2026-10-15)

`client/capsule_capture.py` replaces actor-open polling in native ISOs with a successful-opening event ring at `0x800D4FA8`, the original write of ReleaseBoxSmall's opened flag after item spawning. It captures mission, native context, ORC object ID, instance, Wisp subtype and actor serial while the wrapper still exists. The 32-entry bounded ring publishes payload before sequence/head and reports overflow explicitly. The client validates the installed hook and canonical catalogue identity, persists the check before advancing its cursor, and deduplicates through the existing journal. Captured events retain their original mission across actor disposal and stage transition. Legacy non-native setups retain polling compatibility.

PowerPC simulation verifies identity publication, displaced instruction execution and complete GPR/LR/CR preservation. Queue tests cover actor disappearance, ordering, overflow, incomplete publication and native restart. Runtime integration tests cover deduplication after a stage change. The related regression run passed 86 tests (three existing real-websocket fixtures excluded); the added integration test also passed. The rebuilt capsule-capture ISO passed WIT partition verification. Fast unpaused pickup behavior still needs live verification with this new ISO/client pair; previous polling successes do not establish it.

On the first live capsule-capture boot, binding was blocked because the Act-2 best score improved from 744900 to 752800 while both intro ranks/times, profile and selected slot remained identical. Bound resume now permits only nondecreasing scores with exact existing rank/time witnesses and no loss of recorded clears; 13 binding tests passed, including rejection of score decrease, changed time/rank/profile and clear rollback. After restarting the client, the save resumed and the native capsule ring's first retained event was consumed with no overflow, delivering a new real-server item. Broader rapid-pickup reliability testing remains ongoing.

In the subsequent unpaused Act-3 run, a read-only comparison found 11 native successful-opening events (IDs 408, 242, 183, 437, 646, 387, 449, 297, 401, 430, 419), all canonical/eligible and all already recorded in the pickup journal, with no overflow. This validates those individual fast-run captures, not every capsule path. A separate Rings receipt 69 was marked uncertain after a stable-player write guard rejected its transition context; notification latency and consumable delivery must not be confused with missing location checks. Actor disappearance alone remains insufficient proof because distance unloading can also remove an actor.

## Launcher first-run workflow (2026-10-15)

Update: the earlier existing-instance reuse policy described below has been
replaced on Windows at the user's request. The launcher now sends WM_CLOSE to
the PID-attributed Qt root-owner window, preserves Dolphin's native exit
confirmation, waits up to 60 seconds for process exit, then launches the exact
patched ISO. No force termination or concurrent second instance is used.
Timeout, another arriving instance and ambiguous windows abort startup.
Launcher/container tests pass; an end-to-end live restart is still pending.

Boost crash correction (2026-10-15): the native boost-use hook at 800CD730
incorrectly dereferenced r30+8C. Original 800CD720 stores the wrapper argument
in r30; 80033A44 resolves wrapper+28 -> player+8C before 800381E0 reads
provider+24. The corrected hook follows that chain. The reported low-memory
PC 80001B80 was exactly the second load in the erroneous hook. Executed-PPC
regressions poison the old path and cover locked/unlocked/empty gauges and
Super mode. The released component fingerprint is accepted for rebuilding
existing seed containers with corrected code; existing ISOs are not modified.
Actual post-fix Dolphin dash reproduction remains pending.

`client/dolphin_launch.py` now selects Dolphin's executable once and saves it. The original ISO chooser follows and retains its existing persistence. An unconfigured install receives the first-run chooser and enables startup after executable selection; later explicit disabled startup settings are respected. Cancelling Dolphin selection still permits patching and client launch. Headless use requires an explicit/stored executable. Patch-only mode does not select/start an emulator unless explicitly requested.

When Dolphin is absent, the launcher starts the verified generated ISO with an argument list. When one instance exists, it opens no second instance and does not stop an existing game; the client verifies the loaded seed. If another game or an idle emulator is open, the user opens the generated ISO in that existing window. This is deliberate: Dolphin's standard CLI has no verified existing-instance boot IPC. Multiple instances produce an explicit error. The already-running branch was checked live against PID 25228 and left exactly that one process running; first-run chooser and cold startup have unit-test coverage but still need a complete user GUI run.

The client uses the patch's player name and server address. A test recreating the webhost download's manifest server insertion confirmed the container remains valid. The corresponding 24 launcher/container/package tests passed. The public hosted download plus GUI chooser/cold start has not yet been end-to-end live verified.
