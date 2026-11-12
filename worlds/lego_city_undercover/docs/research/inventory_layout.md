# Stats and character inventory: static and live evidence

Applies only to executable SHA-256 624fed07274bbd105d1d571ecb97a290df6f6f0aff76898c516890da6d136f76.
All listed addresses are module-relative RVAs; no absolute live pointer is reused across runs.
All implemented access is read-only and hash-gated through diagnose.py.

## Currency

The GetPlayerBricks script-name getter references a candidate handler at RVA 0x107c60.
It loads the statistics pointer at RVA 0x1c7a830 and calls 0x3bf70.
That getter selects a 32-bit counter at stats+0x3314 if any byte at +0x335d, +0x335e or +0x3340 is nonzero;
otherwise it selects stats+0x3318. The reader reproduces this branch rather than assuming a permanent offset.

The statistics block also has a 64-bit Stud checkpoint at +0x3348. It held 10,580 while the player's actual balance
was 17,580. It is not the current Stud balance. Static instructions at RVA 0x41620 compare that checkpoint against
the 64-bit value at profile+0xfb10, using the profile pointer at RVA 0x1c7f160.
The latter counter matched the displayed balance and a later controlled change.

GetGoldBricksCollected candidate handler RVA 0x107c20 calls 0x3bce0, which returns stats+0x3660;
the handler reads the 32-bit value at +4. Thus stats+0x3664 is the collected count; +0x3660 held the total 450.
The collected count read zero in both live samples. A Gold Brick acquisition transition is not yet validated.

| Observed snapshot | User screen Studs / Super Bricks | Reader values | Delta |
|---|---|---|---|
| live_inventory_first_read.json | 17,580 / 2,171 | 17,580 / 2,171 | Baseline |
| live_inventory_second_read.json | 17,590 / 2,177 | 17,590 / 2,177 | +10 / +6 |

The second sample was read using the built standalone .pyz in isolated Python mode.
Both snapshots are in ignored notes/analysis; no current save-slot identifier has been independently decoded.
Slot 1 is the user's report, not a value read by the tool.

## Character state

CharacterAvailable candidate handler RVA 0x105b50 resolves model names through 0x834ea0 / 0x834e10.
The model manager pointer is at RVA 0x17ebd38, model count at manager+0xe0, and model pointer table at +0x118.
In the live game count was 1,002. Model records contain their internal name pointer at +0x30.
This includes vehicles, customizer models and co-op alternatives; 1,002 is not a playable outfit count.

RVA 0x88c020 reads a state block through the pointer at RVA 0x1c7cbb8, testing a per-model byte at state+0x80+model_id.
RVA 0x88a290 sets that byte; 0x88a2b0 separately sets the model's bit at the beginning of the state block.
The reader keeps the bit and byte separate. Interpreting the bit as found/token state is based on static action
relationships; a controlled token discovery versus purchase experiment remains required.

The character controller pointer at RVA 0x17ebe20 aliases the model manager in the observed process.
The table at controller+0x148 contains two players' eight default model ids. These include locked classes:
they must not be reported as unlocked merely because a default model id exists.
The 16 signed 16-bit slots at +0x16a hold pending class-character grants (-1 denotes no entry).
The pointer at +0x1a0 and count at +0x1ac describe additional pending character ids.
The class-availability helper at 0x25250 consults pending class ids; the commit routine at 0x23d40
transfers pending class and extra grants into the bit/byte bank and dispatches further engine logic.

At the tested point COP (227) was in the first player's pending police slot, COP_CLASSIC (701) in the second
player's corresponding slot, and Cop_Female_P2 (702) in the pending extra list. Their bank bytes were still zero.
Civilian_ChaseMcCain (244) had its bit and byte set. This explains why a bank-only read missed Chase Police and Grace.
The reader now combines bank and pending evidence while retaining each source explicitly.

The three primary outfit candidates matched the user's reported civilian Chase, police Chase and Grace Makepiece.
Co-op alternatives, non-progress customizer entries and vehicles are reported separately, not discarded.
All possible future roster unlocks, purchases, equipped characters and restart persistence are not yet live validated.

## Roster metadata

GAME.DAT's chars/collection.txt supplies model categories, default-player roles and no_progress declarations.
The generated bridge/collection_manifest.json contains only factual model identifiers/categories/roles, not original
script lines or asset payloads. tools/collection_data.py reproduces it from the user's local resource and records its hash.
The source declares 305 progress-counted characters and 120 progress-counted vehicles.
Some model names are deliberately declared again in another category with no_progress: these aliases are merged,
and the reader does not invent a second collectible for them.

## Equip negative control and check semantics

The user explicitly requires individual character unlocks as checks, never equipment selection.
After switching to civilian Chase in slot 1, live_civilian_equipped_control.json preserved all three primary
character records and pending/default control fields compared to live_inventory_second_read.json.
The currency values also remained 17,590 Studs and 2,177 Super Bricks. This negative control supports
separating unlock evidence from outfit selection; it does not yet validate every possible unlock source.

## Live post-autosave commit transition

After the user reported finishing the save and exiting the station, live_station_exit_navigation_saved.json
showed COP (227) and Cop_Female_P2 (702) changing from pending-only to found_bit=true, owned_byte=1,
pending_grant=false. All 16 pending class slots and the extra list became empty. Primary unlock candidates
remained the same three characters. A future AP detector must not send new checks merely because a pending
grant is committed into the bank. This is observed runtime commit behavior, not yet a reload/disk-save test.
The same snapshot read 19,030 Studs and 2,186 Super Bricks; Act1_Mission advanced 1->2 and Act1_Stage 2->1.
Policestation and SF_Residential ability states changed false->true. No distinct navigation symbol changed.

## First existing-slot reload validation

The user returned to the main menu and loaded existing slot 1. During the replayed station-exit/navigation
cutscene, live_slot1_reloaded_cutscene.json read the same 19,030 Studs, 2,186 Super Bricks and three primary
characters, all bank-owned with no pending grant. Queried global ability states also matched the pre-reload
snapshot. This validates these vanilla-granted characters/counters across this reload, not AP item persistence.
Story values loaded Act1_Mission=1, Act1_Stage=3 instead of the pre-reload 2/1, and LobbyEntered=0 instead
of 2. The cutscene notification replay alone therefore must not create duplicate character/ability checks.
The exact story checkpoint and navigation UI semantics remain under investigation.

After the reloaded cutscene ended, live_slot1_reloaded_control_restored.json still matched the pre-load
19,030 Studs, 2,186 Super Bricks and three bank-owned outfits. All queried ability values matched, and
the office key remained absent. Act1_Mission/Stage returned to 2/1. LobbyEntered remained 0 rather than 2;
that field is therefore not a durable station-completion check by itself.

## First open-world booth/token/Gold Brick transition (2026-11-12)

After the user activated an Auburn booth and reported the mechanic unlock and first Gold Brick,
live_auburn_first_booth_mechanic_gold.json showed Gold Bricks 0->1. The new character row was
Collect_6-09_Mechanic (runtime model 442), found_bit=true, owned_byte=0, pending_grant=false.
Thus the unlock notification correlates here with token discovery, not owned/usable character state.
The user has not yet confirmed the shop UI or purchased this character. AP native-discovery detection
needs to preserve that distinction and must not infer ownership from an unlock popup.

## Mechanic purchase versus discovery (2026-11-12)

Following the reported vanilla purchase, live_mechanic_purchased.json read Collect_6-09_Mechanic
found_bit=true in both snapshots, with owned_byte changing 0->1 and unlock_candidate false->true.
Studs changed exactly 44,110->34,110 (-10,000), matching the collection resource price. Gold Bricks stayed
at 1 and city-objective completion records did not change. Equipped model remained COP.
This is live evidence distinguishing token discovery, ownership and equipped model. It does not prove a
safe AP grant path or immediate native save; AP receipts must bypass the vanilla purchase cost.
