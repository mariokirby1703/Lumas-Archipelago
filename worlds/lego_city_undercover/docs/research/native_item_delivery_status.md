# Native item delivery status

Current implementation: 2026-11-14. Experimental; live effect tests are still required for the newly added currency and suppression paths.

## Implemented

- Opt-in native model grants for characters, primary disguises and vehicles. Ownership is granted without purchasing or marking the original token discovered.
- Two booth navigation patches accept owned OR found. Magician model 270 was confirmed selectable by the user with owned=1/found=0. Lifeguard model 291 was also tested.
- Bound native ability grants (0x90e00) and cheat ownership grants (0x7f19a0, bookkeeping=false). Original cheat discovery and mission reward bookkeeping stay separate from AP grants.
- Exact Studs packages: 1,000 / 10,000 / 100,000. Exact building-brick packages: 100 / 250 / 1,000 / 10,000. Wallet packages bypass pickup multipliers and do not count toward mission Hero studs.
- Native autosave requests after grants, including during unlock popups when the game's save controller permits them. A request is not considered disk confirmation.
- Native save identification by a unique full-character-bank match among Steam slots, or an explicit --native-save-file. The journal binds that exact file and creates an integrity-checked slot backup before the first mutation.
- Disk verification for model ownership, cheat ownership and existing ability flags. Receipts become applied only after their effect is observed in the native file. Applied receipts are still reconciled so restoring an older native save can recover AP effects.
- A persisted currency watermark binds one native save to one AP seed/team/slot/catalogue and suppresses duplicate credits after retries, a lost RPC response, client restart or rollback to an older save.
- Post-check reward suppression for AP-managed model ownership, pending class/extra model grants, bound tool ability flags and cheat ownership/runtime activation. Scope follows seed item-category options and actual received entitlements.
- Check reconciliation and durable outgoing queuing happen BEFORE suppression. Genuine pending character grants are committed as discovered before their vanilla ownership is removed, preserving source identity.
- Shop purchase guards reject AP-managed models before ownership changes or Stud deduction. Both shop price/buy UI paths hide the purchase option for unreceived models. AP-owned models retain their native selection path; unmanaged categories and custom-character mode retain vanilla behavior.
- An unreceived equipped model is never automatically switched or revoked underneath the player. Suppression waits for the user to select an entitled or starting civilian outfit.
- A Windows named mutex permits only one updated native client per Windows session. Text-only viewers and the monitor remain independent.

## Native bindings and persistence evidence

Supported executable SHA256: 624fed07274bbd105d1d571ecb97a290df6f6f0aff76898c516890da6d136f76.

Transport version 2 is 64 bytes, using WH_GETMESSAGE on the game's window thread. No arbitrary function address comes from an AP item. Commands validate process/thread identity, names, indices, model counts, native pointer relationships and function signatures. Mutating grants and suppression require ordinary Default context and a live loaded actor. Save requests and explicitly read-only probes have separate eligibility rules.

- Character ownership: 0x88a290; discovery: 0x88a2b0. The native 1002-model table disambiguates targets. COP/Cop name collisions retain the canonical primary class binding even after a skin change.
- Booth navigation: 0x267fb4 and 0x268202, generated from model_selection.py. The earlier ineffective 0x26e067 experiment is restored to original code. The replacement instructions are tested with actual Windows x64 execution against synthetic inventories and word boundaries.
- Bricks: getter 0x3bf70 and setter 0x40e30 preserve the native city/mission-bank choice and display mirror. Studs: profile+0xfb10, the same persistent wallet field credited by native 0xa003d4 / 0x8ea520.
- Autosave: TriggerAutoSave action 0x87250 calls 0xd18b0 on stats+0x3638. Currency waits for an idle enabled controller before changing balances.
- Native bank aliases 0x811a93..0x811b3b establish character bank=profile+0x122e0 and cheat ownership=profile+0xfa80. The supported 2,579,512-byte HMGR v1 save serializes the character bank at 0x14318. Both pointer relations are checked before currency/suppression writes.
- Currency marker: 22 unused owned-model bytes for indices 1002..1023, ending exactly before bank+0x480. Native model count MUST equal 1002. The marker contains AP magic, a 128-bit binding token and the next server receipt index. Nonzero foreign contents or another binding are rejected, never overwritten. The actual model reader stops at 1002, so these bytes cannot produce character checks.
- Ability serializer 0x90d90 writes type 51 and two uint64 masks; 0x907b0 builds existing and pending masks from manager+D8 / +10B. The unique container signature is 3d4f6d43 12000000 33. Four historical backups each contain it once; all 51 existing bits matched the running game in the latest read-only validation.
- Cheat ownership is verified in the serialized profile+0xfa80 mask. Runtime activation is entry+0x1a. Profile+0xfa78 is NOT an activation bank: 0x6a460/0x80e5b0 uses it for Police_Station pickups. Suppression never touches that source flag bank.
- Tool removal uses native 0x90c80. The unverified equipped-model fallback through 0x890b40 has been removed.
- Shop guards patch complete instructions at 0x264e70 (8 bytes), 0x265b5c (9 bytes), and 0x266139 (6 bytes). Entry model IDs come from the 44-byte collection table at global 0x11827b8; the uint16 count at 0x11827c2 is confirmed by collection loops at 0x7e3627 and 0x7f00c5. Original bytes must match before installation.
- Each persistent guard page contains only self-contained instructions, game addresses and an AP-managed mask. It never calls into the temporary DLL. Existing installations are signature/jump validated before mask updates; failed installation rolls back entry patches.

## Validation

136 tests pass. They cover native instruction replay, generation/pool counts, policy category/alias behavior, real ownership-vs-discovery save semantics, pending-vs-existing ability semantics, immutable backups, persisted receipt ordering, lost native responses, journal restart and older-save recovery without duplicate currency.

The compiled DLL's read-only policy preview succeeded in the running game, with the complete character bank and all existing ability bytes unchanged. Current save slot 1 contains Magician and Lifeguard ownership. No currency packages or nonempty suppression policy were applied to the game during this implementation turn.

Artifacts: build/lego_city_undercover/native_save_and_policy_preflight.json, review_tests.log, LCUItemBridge.dll and lego_city_undercover_experimental.apworld.

## Required in-game tests and remaining boundaries

Next tests: shop purchase UI and attempted purchase for an unreceived character and vehicle, AP-owned selection, wallet stability, and check/save/reload. Test a new vanilla disguise/ability/cheat unlock separately; automatic character fallback is disabled. Vehicle selection and other character/ability/cheat cases remain individually unverified.

Suppression is polling after checks, normally once per second, and defers while the player is busy. It is not a hook preventing the original reward animation or every first-frame interaction. Normal resource pickups, objective completion, gold bricks and original source discovery flags are retained.

Only bound tool flags are suppressed. Story/map/mission bookkeeping flags are excluded. Symbolic Carry Objects, Climbing, Crowbar, Fishing, Stethoscope and Rex Fury effects remain explicitly unbound and are logged as waiting; this work does not invent native flags for them. Full co-op behavior is not validated.

Story entrance locks, area/object appearance locks, open-world initialization and full generation access logic remain outside this implemented delivery layer. The monitor EXE remains read-only; the source client and compiled DLL provide native delivery.

Currency backlog optimization: up to 24 ordered packages are credited in one native command, with one combined autosave. The native watermark skips previously credited indices before summing amounts; both balances and the final receipt marker are updated before requesting save.

## Purchase/crash correction, 2026-11-14

The user observed a purchase becoming selectable until the menu reopened, then reverting to unpurchased. Poll-based ownership revocation did not prevent spending or immediate selection. A Windows Application Error recorded LEGOLCUR_DX11.exe exception 0xc0000005 at RVA 0x834275 (virtual call through an object pointer). Two native clients were also running; both were stopped. The crash cause is not established. The automatic actor switch was removed as an unverified mutation, and the updated client prevents duplicate instances.

The five new tests execute the generated x64 guards against synthetic shop records in the test process (no game access), exercise mask boundaries, unmanaged/custom modes and owned selection, and compare generated C++ relocations against the Python builder for image/guard pages above and below each other. Full suite: 136 passing. DLL rebuilt successfully. Actual game UI and crash resolution still require the next live test; no claim of a crash-free game run is made.

## Reconnect regression, 2026-11-14

A supplied client log showed a successful AP connection and disk-verified native character grant, followed by server disconnect. CommonClient.server_loop recursively retries ws using wss. Both outer and inner finally blocks previously reset the connection and scheduled autoreconnect, triggering an AssertionError because the inner loop already created that task. The TLS retry now owns lifecycle cleanup; the outer loop skips duplicate cleanup. This is a shared CommonClient.py source fix, used by the source launcher; it is not embedded in the APWorld. Three async regression tests cover TLS connection/disconnect, TLS refusal, and ordinary refusal. Full suite now passes 139 tests. A direct TCP check confirmed the reported host/port accepts connections again; slot authentication was not attempted.

## Busy interaction deferral

The next user log confirmed Red Brick CHEAT_SCAN_CHAR_CHALLENGE sent its location check and AP receipt 103 credited 1,000 Studs with native disk verification. Native return code 3 was intermittently raised when the player context changed after the host snapshot. It now raises NativePlayerBusy and is handled inside NativeDeliveryEngine.poll as a normal deferred operation. The watcher retains its session and previous check snapshot; pending receipts remain queued. Other native errors still propagate. Two regression tests verify retained engine state/retry and propagation of actual errors. Full suite: 141 passing. No native DLL change is required for this host-side fix.

## Main-menu cutscene skip startup

The client now attempts the opt-in N0CUT5 permission before a full player/save snapshot, once connected slot options enable cutscene_skip. Missing/uninitialized cutscene managers defer without resetting the reader. Initial success is logged even if permission was already enabled. A snapshot without a validated loaded actor cannot enter check evaluation or native delivery; inventory remaining in menu memory is ignored. Three async tests cover skip before any save/player, stale menu inventory rejection, and the disabled seed option. Full suite: 144 passing. First-intro behavior still requires live confirmation; restart the game before connecting a new seed to Slot 2 so Slot 1 actor state and prior native patches are cleared.

## AP-owned character subcategory availability

Live read-only probe in Slot 2: Tiefseetaucher/COLLECT_1-15_DEEPSEADIVER, model 276, owned=1 and found=false. Its category 8 availability bytes at arrays global 0x17ebfc8 and 0x17ebfd0 were 0; the genuinely discovered Mechanic's category 9 was 1. The native discovery callback 0x258c0 reaches 0x26af0 and marks these category flags, whereas the ownership callback 0x25870 does not. This explains why owned-only booth navigation patches alone were insufficient for a fresh category.

A new self-contained category availability guard at 0x26210 preserves genuine category flags and derives additional availability from owned collection entries in that category (progress-counting bit 8 in record+0x16, category record+0x17, model bounds <1002). It never invokes the discovery callback, marks source bits, changes class defaults or unlocks unrelated categories. The temporary DLL contains no persistent callback target; game-owned executable memory holds the guard. Live category-selection confirmation remains pending.

The running game retained the old DLL mapping, so the new bridge was built as LCUItemBridgeCategory.dll. The source client and launcher resolve dll_filename from native_items_build.json; no game restart is needed solely to select the new DLL. Restart the native client, leave the booth until ordinary gameplay so policy installation is eligible, then reopen it. If the runtime rejects installation, it remains an explicit error rather than claiming menu success.

Two native execution tests cover AP-owned category eligibility without discovery writes and existing native flags/model bounds. Two artifact resolver tests cover default/parallel DLL selection and rejected paths. Full suite: 148 passing. Astronaut design clarification: the user wants a progressive Astronaut item, first class, then Jetpack; this supersedes the earlier assumption of two separate item types and is not implemented by this category fix.

## Corrected category counter and label (supersedes prior category-flag guard)

The user's live test disproved the previous category-flag solution: Spezial 1 had a name but could not be entered, while Spezial 2 said locked but could be entered. Live arrays showed category 8 owned count=1 / source-found count=0, and category 9 owned count=0 / source-found count=1. The separate arrays are globals 0x183fc50 (owned) and 0x183fc58 (found). The previous hook at 0x26210 concerned notification flags and did not correct menu selection. It is now validated and restored to original bytes; its allocated page is retained to avoid freeing potentially in-flight code.

The new patch changes the derived UI count rebuild at 0x265489 to increment eligibility for either source-found or owned models. It does not set source bits or inflate the actual owned count. The mode-3 category label's pointer at 0x26f2c3 reads that same union count instead of owned-only, so genuinely found but unpurchased categories retain their names. Existing per-model purchase and entitlement gates remain intact. All original bytes are validated before patching. category_selection.py is the source for generated native patches.

Two new tests execute the actual count guard with synthetic native banks across 32-bit boundaries and verify no inventory writes, plus the label's RIP target. Full suite: 150 passing. Built LCUItemBridgeCategory2.dll; live selection confirmation remains pending. Restart native client, leave booth for ordinary gameplay so the new policy path can install, then reopen the booth to rebuild counts. The obsolete category getter generator remains only as a legacy signature/compatibility reference, not an installed solution.

## Passive AP grants while riding/driving

User reported checks/rewards became credited/saved only after leaving a vehicle. Journal inspection at investigation time showed seven outgoing checks acknowledged and no waiting deliveries. The watcher already reports checks before native delivery, with no Default-context restriction on check detection. NativeDeliveryEngine and the DLL did restrict grants to Default (46). Live read-only actor state was Tiefseetaucher model 276, context RideObject (157); DropPoint (27) is the other previously observed vehicle-related context.

Host and native eligibility now allow passive model, bound ability, cheat ownership and currency grants in Default, RideObject and DropPoint. Reward revocation/policy enforcement is still Default-only and is skipped in riding contexts. Native health, loaded actor, pinned process, binding, save identity and save-controller checks remain active. Unknown interactions/death states are not broadly enabled. Shared native_context_policy.py generates the C++ context guard. Saves still require actual disk proof and retain receipt watermark deduplication.

Tests cover currency application/disk verification/recovery in both vehicle contexts without enforcement, host check queue/send from RideObject, eligible opcodes versus death/interaction contexts, and all existing cases. Full suite: 155 passing. Build: LCUItemBridgeVehicles.dll. Actual in-vehicle receipt and disk confirmation still need a live test after restarting the native source client. No vehicle or actor replacement was added.

## Early police-station exit without granting Police

Live state: Flow_Act=1, Act1_Mission=1, Act1_Stage=2, lobby entered once and mainframe inactive. The fresh AP player had no Police entitlement, so the vanilla tutorial cannot be completed yet. Normal free hub scripts are enabled after exit_lcpd.sf finishes the tutorial. Enabling HUB_LCPD.HubActive broadly was rejected because hub_lobby.sf resets other story/job fields.

The normal scripts HUB_Lobby2CityTransition.sf and LCPD_BriefingRoom.sf leave via POLICE_LOBBY_EXTERNAL_DOOR.Trigger(). Read-only native inspection located the existing door in the loaded lobby, owned by GizmoDoorManager. GizmoAction_Trigger at 0x9e84c0 calls the object's virtual +0x210; for this exact door vtable 0xd5fc98 this is 0x8a1780. The new bounded opcode 12 uses that exact existing transition, rather than teleporting an actor or marking a mission finished.

Host scope is the early Act 1 mission 1/stage 2 only. The gate first requires walking farther than 4 m from the door, then returning within 2 m while Default context, preventing automatic ejection at an entrance spawn. One attempt is latched before RPC dispatch so a lost response cannot replay a transition. Native code independently revalidates alive Default actor, actual scene Police_Station_Lobby, registry, scene manager vtable, unique door name/owner, finite transforms/distance, actor transform accessor, door trigger vtable slot and function prefix. It accepts no caller-provided pointer or target level. No AP completion flag, Police model or story Job value is written.

Five gate tests cover arrival, arming, scene/process changes, interactions and one-shot behavior. Three additional native tests compile and execute the real helper against an artificial lobby and harmless trigger counter, checking valid dispatch, other scene/distance rejection, wrong owner/list cycle/signature rejection. These do not open or modify the game. Full suite: 163 passing. Built LCUItemBridgeStationExit.dll. The actual game transition remains pending after source client restart and user walking away from, then back toward, the front door. Native function invocation is a transition request, not proof of successful city load.

## Station exit packet dispatch regression

The first live exit attempt timed out because ItemBridgeHook still accepted only opcodes 1..10, excluding the new exit opcode 12 before dispatch. The helper tests had not exercised the hook's admission gate. Read-only inspection confirmed the player remained in the lobby. This was an implementation error, not evidence of a blocked native door transition.

A shared ClaimCommand helper now implements the real hook's magic/version/opcode/PID/thread validation and atomic pending-to-executing claim. The allowed opcode set (1..10 and 12, excluding unused 11) is generated from native_context_policy.py and also validated by host transport. Two native fixture tests exercise this exact production helper, including exit acceptance exactly once and rejection of unknown commands/wrong identity. Timeout diagnostics now include opcode/name. Full suite: 165 passing. New build LCUItemBridgeStationExit2.dll.

A one-shot live attempt after the fix was deliberately not dispatched: the latest read showed RideAlong context 11 and door distance squared 50.317, outside the native exit range. No transition or story value write was performed. Live successful exit still needs confirmation when the player returns to the entrance in ordinary gameplay after client restart.

## Police lobby toy-car activity

The user completed the police toy-car ride to the right of the lobby and received a Gold Brick. Native objective entries LCPD_Lobby_RideOn01 (bit 713) and RideOn02 (714) were both true; these were previously raw Clue prerequisites, not a validated separate pair of AP activities. The specific reward object GB_RideOn was observed collected, native type 11 / flags 0xf, with resource source GAME7/levels/standalones/police_station/police_station_lobby/police_station_lobby.giz:16117:42 and resource coordinates (2.947598,0.826614,-2.269449).

activity_rewards.json now defines one named city_activities check, Police Station Lobby: Toy Police Car Ride, bound to that exact scoped reward object. It does not watch the global Gold Brick total or create separate locations for the two hint flags. The source identity is supplied by city_pickup_sources.json and reproduced by its generator. The catalogue builder promotes this existing source candidate and removes duplicate raw RideOn clues. The client reports/logs recognized activities even when absent from current slot_data; only locations actually present in the server seed can send AP checks.

A fresh read-only native probe using the new detector recognized police_station_lobby:toy_vehicle_ride in the current game. The running seed's journal catalogue contains no RideOn location, so it cannot award an AP item retroactively without generating a new seed. Existing gameplay can continue and this observation is retained. Three tests cover one-time check reconciliation, no false positives from room/type/name/source or duplicate objects, and generated activity category/no duplicate prerequisites. Full suite: 168 passing. Updated APWorld built; native DLL unchanged.

## Lobby re-entry incident and constrained resume repair

The user left via the inserted exit and re-entered. The lobby incorrectly ran its garage-return setup and requested Police mainframe interaction. This is a real flaw in the first exit implementation, despite its use of the existing door function. lcpd_lobby.sf selects its script from LCPD_LobbyEntered (0=first, 1=garage-return) and increments it at every entry. The AP shortcut had left it at 1; return therefore ran LobbySecond and raised it to 2. Read-only incident capture confirms Flow_Act=1 / Act1_Mission=1 / Act1_Stage=2 / LCPD_LobbyEntered=2 / LCPD_MainframeActive=false, with no later mission progression.

Both matching native-client processes were stopped to prevent another old automatic exit. The auto path was removed while investigating. A fresh immutable backup of all three Slot 2 native files was made at notes/save_backups/slot2_before_lobby_recovery_1794637061853643400; current state was captured in build/lego_city_undercover/lobby_reentry_incident.json. No save rollback, AP receipt rewrite or live JobValue mutation was performed during diagnosis.

The corrected escape is deliberately limited to the verified pre-mainframe state: act 1 / mission 1 / stage 2, MainframeActive=false, LobbyEntered 1 or 2. Host can_resume_first_lobby checks this before proximity arming. Native lobby_resume.h independently resolves exact named JobValue records with table limits, unique hashes and Int/Bool vtables. Only immediately before the validated exterior-door trigger does it set LobbyEntered to 0, preparing the next genuine first visit. It does not change mission/stage, mainframe completion, class/item entitlements, gold count or check bits. Later/unknown phases fail closed. This includes the already-misrouted state 2/false, so the next corrected exit prepares recovery without restoring an older inventory/save.

The direct int store matches JobValueInt::Assign at 0xda1b0, which stores at object+0x10 without extra callbacks. Native fixture tests exercise field resolution, repeated first-visit preparation, the incident state 2/false, and rejection of later/unknown phases without writes or a trigger. One host eligibility test was added. Full suite: 171 passing. Source client now uses the constrained resume-aware path; new bridge LCUItemBridgeLobbyResume.dll. A real leave/re-enter cycle remains untested. The client is still stopped and no further live exit was invoked; the user must deliberately restart and test the corrected route.

## Lobby exit proximity tuning

User confirmed the resume-aware exit but reported its lobby trigger was too broad. Host and native distance limits now require a radius of 0.8 m from the existing door anchor, reduced from 2 m. Arming requires stepping more than 2 m away (previously 4 m). Existing tests now reject the 1.2 m lobby distance in both host and native code while accepting the doorway point. Full suite remains 171 passing. Built LCUItemBridgeLobbyExitTight.dll; live feel of the smaller zone needs user confirmation.

## First-visit mainframe phase correction

The user reported no exit after the zone reduction. Live read showed door distance 0.445 m, Default context, LobbyEntered=1 and MainframeActive=true. The radius was reachable; eligibility was blocking the known first visit after its mainframe repair. lcpd_lobbyfirst.sf sets MainframeActive before moving Frank to the lift, so it is not a garage-visit marker. Both host/native guards now accept first visit (counter 1) with either Boolean mainframe state and preserve that flag while preparing counter 0. The incident rescue counter 2 is still accepted only when MainframeActive=false; later/ambiguous phase 2/true remains blocked. A native test covers first/true and confirms the flag stays true, plus rejection of ambiguous second/true. Full suite: 172 passing. Build LCUItemBridgeLobbyPhase.dll; smaller 0.8 m zone retained.

## Garage lift return without Police ownership

User was blocked in Police_Station_Garage next to its lift, without Police model 227 ownership. Live native door list confirmed POLICE_GARAGE_DOOR uses the same validated door vtable 0xd5fc98/trigger 0x8a1780. lcpd_garage.sf states ToLobby and ToFadeLobby call this exact door's Trigger normally. Live state remained act 1 / mission 1 / stage 2, LobbyEntered=1, MainframeActive=true.

The existing station transition command now has a second fixed route: garage -> lobby via POLICE_GARAGE_DOOR. The garage proxy is inactive if Police is already owned, leaving the normal tutorial in control. The same resume guard prepares counter 0 before return, so it does not falsely enter LobbySecond or claim that the uniform was collected/equipped. Mainframe repair, mission/stage and entitlements remain unchanged. Host/native route whitelists reject other rooms/doors.

The garage's usable trigger center is 0.6 m in front of its door anchor along local resource X, because the closed lift collision leaves the standing player about 1.2 m from the anchor. The small 0.8 m radius applies around this accessible center; arming still requires moving more than 2 m away first. A live read-only probe using the new detector found the exact garage lift with distance squared 0.4063 and resume eligibility true. No live transition was invoked during development.

Two native fixture tests cover garage return without Police and preservation of first-lobby/mainframe state, and rejection once Police is owned or the player is outside the lift zone. Full suite: 174 passing. New bridge: LCUItemBridgeGarageReturn.dll. Live return and correct lobby setup remain pending after source client restart and walking away from, then back toward, the lift.

## First-lobby lift arrival doors

After the garage return, the user spawned behind closed lift doors because LobbyFirst does not run LobbySecond's arrival animation. lcpd_lobbysecond.sf opens the existing GizObstacle DoorsOpening and disables DoorsClosing; starting that whole script would incorrectly assume the later tutorial state. Live read located both exact obstacles under the lobby's obstacle manager (slot 1, vtable 0xc2e468; objects 0xc2dec8). Both flow interfaces at +0x108 match 0xc1ba18.

New opcode 13 OPEN_LOBBY_LIFT is admitted by the shared packet dispatcher. Its native guard requires first-lobby phase/count 1, exact lobby scene, living Default actor (outer guard), unique named animation pair, bounded manager list, correct owner/vtables and actor within 1.5 m of the lift. It uses native setter 0x77d3e0 on each flow interface, matching GizmoAction_SetActive at 0x9e83a0: closing inactive, opening active. It never changes story values, grants Police, starts LobbySecond or invokes another level transition. The source client attempts this once per lobby owner when near the lift; garage/city scene changes clear its latch.

Two native fixture tests verify the actual helper calls both animation setters with the correct values, preserves visit counter and does not trigger a level load, plus wrong scene/distance/visit rejection. Packet admission tests now include opcode 13. Full suite: 176 passing. Build LCUItemBridgeLiftArrival.dll.

A guarded one-shot live command was executed at the user's trapped position: distance squared 0.02450, Default, eligible phase. The native command returned lift_open_requested=true. This verifies dispatch and native setter invocation, not yet the user's ability to walk through the opened doors. User confirmation remains pending. Source client must be restarted for automatic handling of future arrivals.

## Two early station pads without Police (2026-11-14)

Opcode 14 clears only the Police requirement mask of the uniquely identified
Garage Cop_UseKeypad_SW instance at (5.5669465,-0.178157,-3.9803517), after the
genuine COP discovery bit. The lobby MF_Switch additionally requires the typed
PDA.acquired flag; the original garage script sets this at ActivateLiftDoors
following the Ellie sequence. No other interaction requirements are removed.

Live testing confirmed the generic garage pad could be used, but it remained
repeatable without advancing. The running lcpd_garage script was still in
LoopChangeClothesHint, whose condition requires an equipped COP model. The bridge
now schedules ShowCostumeWheelHint using the same native 0x653b60 operation as
SAction_GotoState and restores the original successful condition's P1 swap flag.
It validates the owner, ScriptJobComponent manager/contexts, exact current state,
target state kind and zero scope-pop count, and requires the garage script's
ActivateLiftDoors state. Other states and pending transitions remain untouched.
ShowCostumeWheelHint and FrankMoveToShop still test the real complex keypad
GetOutput(0). Neither keypad completion nor PDA.acquired is synthesized. The
already used pad may need using again because its prior output was not consumed
while the script was waiting for an equipped Police character.

Live: garage mask changed 0x10100000 -> 0x100000; user confirmed usability.
The user confirmed the lesson correction advances the Frank/Ellie sequence.
A subsequent read found the original script in CutsceneEnded with no pending
goto. Lobby pad end-to-end test is still pending.
182 tests pass, including native synthetic-memory tests for source gating,
PDA gating, preserving outputs/other fields/class ownership, exact lesson-state
selection, pending/nested/other-state rejection and native signature/list-cycle
rejection. Build: LCUItemBridgeTutorialFlow.dll. Restart the source client for
automatic maintenance and the later lobby patch; same seed and save remain valid.

## Completed-basement exit regression (2026-11-14)

User reported that returning with the temporary garage exit replayed Frank's
first lobby setup. Live read confirmed PDA.acquired=true, LobbyEntered=1 and
LobbyFirst's LobbyInstruction running. The early exit reset did not previously
check PDA.acquired; this was a bridge bug. Both host eligibility and the native
EarlyLobbyResumeCounter now require a present, typed, false PDA.acquired value.
After actual basement completion, the temporary exit and its counter reset are
disabled. Missing/invalid PDA state also rejects the temporary route. The normal
garage ReturnToLobby/ToFadeLobby script owns the transition thereafter. Mainframe
pad relaxation still requires PDA.acquired=true, independently of this exit gate.

183 tests pass. Regression tests cover both exit routes after PDA acquisition,
verify no trigger and no selector reset, and cover host missing/true PDA values.
New selected build: LCUItemBridgeCompletedBasement.dll. A running old client must
be restarted. The already loaded first lobby is not retroactively replaced by
this guard; its correct second-visit setup needs a scene reload. No mission,
PDA, entitlement or active lobby job is rewritten by the fix.

## Tutorial floor-symbol correction (2026-11-14)

Removing the Police requirement also removed the branch that selects the central
floor sprite, leaving only the rotating ring. The two scoped tutorial pads now
use the native custom-sprite bit 0x80000000 and signed-short sprite ID 632 at
+0x3fa. RVA 0x800a0 selects this sprite independently of Police class availability;
the artwork remains the original unlocked police-pad symbol. No Police permission
bits are restored. Garage flags become 0x80100000; lobby flags 0x80000000, only
after their existing COP-discovery/PDA gates. Activation and output state remain
untouched. Native permission code 0x7f3f0 does not use bit 31 as a class requirement.

184 tests pass, including custom marker selection with Police unavailable and
idempotent application. LCUItemBridgeTutorialIcons.dll was built and one scoped
change applied live; rendered appearance awaits user confirmation. Client restart
selects the new bridge for future scene loads. The completed-basement exit guard
from the preceding build remains included.

## Center icon: previous sprite-only fix was incomplete

The user confirmed that the sprite-only change above did NOT restore the visible
center. Readback showed +0x3fa=632 but +0x3fc=-1. Static inspection located the
independent action-icon selection routine at 0x466f0: its custom branch reads
+0x3fc (0x469fa), while 0x800a0 reads +0x3fa. The native original Cop center-icon
resource is resolved through the int at RVA 0x1176600 (0x46b94), currently 580.
The correction now sets both values after the same exact pad/source gates,
validates that the runtime center icon is in signed-short range, and preserves
activation/outputs and the removed Police requirements. No broad marker reset,
resource reload or story transition is used.

185 tests pass. New build LCUItemBridgeTutorialCenterIcon.dll was applied live;
readback confirmed garage flags 0x80100000 and marker pair (632,580). Rendered
appearance is pending the user's second test; memory readback alone is not
visual confirmation. The previous sprite-only build is superseded.


The second visual test also FAILED, including after walking 5 m away and back.
Read-only revalidation found the exact modified keypad in the engine selection
slot, with player distance 0.00518 m and matching native distance squared. This
confirms the interaction target strongly, but does not identify the renderer of
the visible rotating ring. Neither custom-marker change is a verified visual
fix. See notes/analysis/tutorial_pad_visual_failure.json.

## Screenshot-confirmed floor-ring failure; return to original generic-pad policy

The user supplied screenshots of both the garage keypad and lobby mainframe:
rotating floor arcs remain visible but their center graphics are absent. They
also reported that the first late-applied generic-pad change displayed correctly
before returning to the main menu. The custom marker-ID experiments are therefore
not a verified fix and are superseded. The scoped helper again clears only the
Police requirements (Garage 0x100000, lobby 0), also clearing our custom bit/known
injected marker values when present. Story gates and the completed-basement exit
regression fix remain intact.

A host-side timing mitigation waits for eight seconds of a stable readable scene
before requesting the pad change. It resets on scene identity changes, reader
failure/reconnection, and process changes. This tests the hypothesis that early
patching interferes with the native floor marker's initial creation; it is NOT
an observed engine-ready signal or a proven rendering fix. Native permission and
story predicates still validate independently at dispatch. No native graphics
reset, arbitrary object hiding or story completion is performed.

187 tests pass, including failed-custom-value cleanup without output changes and
timing tests for normal polling, scene/process changes and unresolved scenes.
Build: LCUItemBridgeTutorialSettled.dll. The source client must restart to select
this build and timing policy. Visual restoration remains pending a live test.

## Chief-office key without Detective Scan

The user requested access to Dunby's office without obtaining Detective Scan.
Live state was Act 1 mission 1/stage 2, PDA acquired and synchronised, LobbySecond
in DetectiveHint and the dedicated detective job in FirstJunction. The player
stood 0.326 m from Story_02_LobbyLock. The original M02_Dspot_key_item already
existed in LegoCityItemManager (slot 5, manager vtable 0xc2b878, item 0xd748c8),
but was inactive/hidden (flags 0x1000) at (3.4789503,1.6134267,2.1848316).

Bound opcode 15 CHIEF_KEY requires those typed PDA/story predicates, the actual
Police_Station_Lobby scene, exact owner-validated item/lock objects, and player
within 1.5 m of the chief lock. Both original script transition plans are fully
validated before mutation: DetectiveHint or WaitForDspot -> WaitForChiefLock in
LobbySecond (signature ChiefAwakesMinicut); FirstJunction -> Ended in the detective
job (signature Key_PickedUp). It uses native SetActive on the existing item's
flow interface and native script GotoState scheduling. No new item is allocated,
no key is attached directly, no scan ability, scan objective, AP receipt, mission
completion or door-open output is fabricated. The player still collects the
physical key and uses the original Techno lock. Pending transitions and later
story states reject repeat application.

190 tests pass, including activation plus both state requests exactly once,
before-sync/distance rejection, invalid state scope/native signature rejection,
and real hook admission for opcode 15. LCUItemBridgeChiefKey.dll applied live:
readback showed original key flags 0x1003 (active/visible), detective job Ended,
and normal lobby flow subsequently at WaitForRadioBuildit. User pickup/door test
is pending. Source client restart enables the same behavior on future relevant
visits; same save and seed remain valid.

## Chief radio parts after scan-free key access

User confirmed the original key could be picked up and the chief-office door
opened. They then reported missing music-system parts. Live inspection found
RadioBuildit (GizmoSpellIt manager slot 3/vtable 0xd769c8; object 0xd76478) at
(-3.1311347,1.7847353,2.4298434), flags 0x1000: present but inactive/hidden.
Radio_temp and RadioTable_TEMP were also hidden, as expected until assembly.

Opcode 16 CHIEF_RADIO requires synchronised PDA, actual lobby scene, exact
owner-validated RadioBuildit and the original LobbySecond WaitForRadioBuildit
state (with ChiefAwakesMinicut and WaitForChiefLock signature states). Within
2 m it activates/shows only the existing build object using native SetActive.
It does not complete the build, open another door, grant an ability or schedule
a story transition. Already active/visible objects and other story states are
no-ops. Client maintenance includes the helper after the scene settle gate.

192 tests pass, including one-shot activation without build completion/state
advance and rejection of wrong state/distant player. Build selected:
LCUItemBridgeChiefRadio.dll. Live activation changed RadioBuildit to 0x1003;
user confirmed the pieces are visible AND can be assembled. Key pickup/door
opening and radio visibility/build interaction are now live confirmed. The later
wake-up cutscene/story completion is still handled by the original script.

## Three opening clown arrests as individual locations

The user requested one check per opening-story clown arrest and had just caught
the first with no AP check. Live read confirmed Act_1_CatchRobber_1=true and the
other two false under Flow_Setup.Flow_Completed. The original scripts
chase_bank_robber.sf, scan_first_robber.sf and search_areas_for_robbers.sf set their
respective flags, then autosave. These sources are independent of character
unlocks, gold-brick totals, later story advancement and player equipment.

New catalogue keys (category story_missions, existing YAML option):
- story_arrest:clown_1 / 1265827268 / Story Arrest: Clown Robber 1
- story_arrest:clown_2 / 1866262459 / Story Arrest: Clown Robber 2
- story_arrest:clown_3 / 1595482323 / Story Arrest: Clown Robber 3

story_arrests.py accepts only explicitly true typed flags from a readable story
snapshot. The reconciler includes completed arrests on first connection and after
offline progress, excluding acknowledged/pending checks through the existing
journal/server path. Client logging also names completed arrests whose locations
are absent from the current server seed, rather than silently appearing to miss
them. No arbitrary existing location is substituted for a newly added check.
Existing generated seeds do not contain the new locations; generating a seed
with the updated APWorld and story_missions enabled includes them.

196 tests pass, including individual flags, offline reconciliation, acknowledgement
filtering, invalid/missing values, absent current-seed locations and catalogue
bindings. A read-only live run of the actual reconciler recognized exactly Story
Arrest: Clown Robber 1. No check was sent by this diagnostic. APWorld rebuilt;
no native DLL changes were needed for these existing readable story values.

## Opening logic and guaranteed early Police in linear seeds

User requested all checks reached in the fresh test so far, plus the green clown,
as accessible without Police. They explicitly confirmed green means arrest 1.
opening_no_police.json records the 11 acknowledged keys from the current Slot 2
test journal plus the separately observed lobby toy-car reward and clown arrest 1
(13 source keys total). These are observations about Police requirements, not a
claim that all other item/area/resource requirements have been fully modeled.
The catalogue annotates those exact keys; stable location IDs are unchanged.

For story_mode=linear, generation puts enabled observed opening locations in an
ungated opening region. Other experimental checks are provisionally placed in a
region requiring Ability: Police OR Character: COP. pre_fill reserves one actual
local Police item from the existing pool on an enabled non-excluded opening
location, preferring Ability: Police and accepting Character: COP when ability
items are disabled. Both native delivery plans unlock the same COP model. This
ensures Police can be obtained by the first/green clown checkpoint without
placing it behind its own entrance rule. There is no additional/duplicated item.
Already precollected Police satisfies the guarantee. Missing Police items, no
valid opening locations, and all Police alternatives forced non-local produce
clear generation errors rather than silently overriding settings or making an
unbeatable opening. Open-world mode retains the prior unrestricted catalogue.

202 tests pass, including actual restrictive fill/beatability, no-Police opening
reachability, reachability after either Police receipt, local early placement,
character-only item pools, excluded locations, no eligible checks/items, non-local
conflicts and unchanged open-world behavior. Slot data exposes partial opening
logic and the selected early Police location. This changes newly generated
seeds; the existing hosted seed's item placement is not rewritten. No live game
memory or AP receipt was modified for this logic task.
