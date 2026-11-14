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
