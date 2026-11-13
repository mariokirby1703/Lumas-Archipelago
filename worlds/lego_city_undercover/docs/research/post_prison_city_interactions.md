# Post-prison city interaction observations

Source: user_monitor_post_prison_city_interactions.json (ignored notes/analysis),
1128 cumulative monitor records. New free-roam observations begin around 03:33
on 2026-11-13. Earlier prison observations in the same log are not new events.
All observations are read-only; no game code called or process writes performed.

## Persistent flags and character discoveries

| Time | Native name | Bit / model | Observed change |
| --- | --- | --- | --- |
| 03:34:00 | SF_RD_1022_TrainStation | bit 373 | false -> true |
| 03:34:14 | WI_FO_0702_TrainStation | bit 386 | false -> true |
| 03:34:45 | NPC_CopTraining01 | model 497 | found, unowned |
| 03:37:46 | NPC_SecurityGuard02 | model 426 | found, unowned |
| 03:41:47 | NPC_TrainDriver01 | model 436 | found, unowned |
| 03:49:25 | WI_FO_0702_BearPuzzle | bit 594 | false -> true |
| 03:49:33 | WI_FO_0702_Tent01_BI | bit 595 | false -> true |
| 03:58:36 | WI_FO_0803_ATM | bit 41 | false -> true |

User supplies displayed character names Butch Patterson, Wachmann, Zugführer Bill.
Associate the three discoveries in that order as reported/display-name candidates;
internal IDs and found/unowned status are independent native evidence. Do not
convert a correlated activity reward character into an additional AP location.
Both station flags changed while the reported native location was still Cherry
Tree Hills; a flag's source district and the actor's current district differ.
User explicitly reports two activated stations; route-link semantics still matter
before treating arbitrary paired station changes as separate player actions.

17 Super Brick bit-change events: 6752,361,352,364,672,363,373,368,374,371,682,
683,680,684,681,372,970. These are pickup bit IDs, separate from objective bit IDs.
Four WI_FO_0902 clue changes coincide with pickups 683/680/684/681 respectively:
Brick_ShrineClue / Brick_CrabClue / Brick_PreserverClue / Brick_DumpsterClue.
This is a time association, not proof that the clue is a distinct AP check.

## Ordinary objects and gated interactions

| Native selected object | Requirement flags | Selection result evidence |
| --- | --- | --- |
| #cg_234_AXE_DOOR_SWITCH | 0x110200 | repeated 1; user reports locked axe field |
| #cg_23_Flower_Bed_Switch | 0x100801 | repeated 1; user reports locked farmer watering |
| #cg_106_Fish_Throw_SW | 0x80000000 | 1 before fish; 3 after fish obtained |
| #cg_62_Mini_Fishing_SW | 0x900000 | 3; Fishing context also recorded |
| #cg_62_ATM_USE_SW | 0x900040 | 0 in selected observations |
| #cg_59_ATM_SMASH_SW | 0x110080 | alternates 0/3 before completion |

The native selection result is a multi-valued eligibility result. In particular,
the ATM 0/3 values must not be relabeled intact/destroyed or used as completion
checks: 3 is seen repeatedly before objective bit 41 changes. The actor changes
outfits/tools repeatedly in this interval. Preserve that distinction when adding
AP gates. The city ATM flag is the source completion candidate; the Gold Brick
and the reported 1/18 statistic are companion results, not extra locations.
Field marker predictions for the axe and watering flags correspond to the locked
fireman and farmer variants; this supports the branch mapping without proving
actual marker visibility in every case.

## Attached quest-item definitions

| Added | Removed | Native definition |
| --- | --- | --- |
| 03:45:06.038 | 03:45:14.746 | #ex_301_Valve_Handle_item |
| 03:47:43.143 | 03:47:52.962 | #ex_347_key_item |
| 03:48:57.195 | 03:49:15.730 | #ex_348_Orange_Fish_item |

Attached item presence is not a general hand query. User reports holding and
using these objects. Fish removal is followed by BearPuzzle completion; do not
globally equate any Orange_Fish_item removal with feeding a bear.

## Scan and context evidence

Both DetectiveMode and CriminalScan markers are named successfully in this log;
conversation scan has not been observed here. Registry presence is still distinct
from exact aura occupancy. Scene readers have 70 read states and one unavailable
state while no player was loaded; scan readers have 42 read states and three
unresolved transient reads (two instability guards, one invalid bounded read).

Additional observed contexts include Fishing (13), BenchPress (9), RideObject
(157), Whistle (251), Tube (92), SuperCarry (141), Techno (138), SpellIt (165).
The user additionally reports chewing gum, turning valves/keys, tent construction
and other interactions. A shared context does not uniquely identify these actions;
leave their exact object/action mapping open unless supported by source identity.
No new reader or universal action classification is claimed by this document.

## User-confirmed character display names

- Sam Penn: NPC_CitizenMale07, model 387, found at 05:50:08 in the later cumulative
  city log. The user explicitly supplies this name for that discovery.
- Rob Shepherd (user-corrected spelling): NPC_CitizenMale_NEW_01, model 704, new discovery
  at 05:52:22, native tile WI_Forest_0601, player position
  (-250.713394,14.911592,391.739014). Found=true, owned=0, pending=false.
  Source log: user_monitor_sam_penn_rob_sherperd.json under ignored notes/analysis.

These display names are user observations linked to native model discoveries,
not independently decoded localization strings. Preserve the native IDs/names.
