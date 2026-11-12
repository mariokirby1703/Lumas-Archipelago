# Open city with AP-gated story entry points

User requirement: after the intro, allow city exploration with story-dependent world
barriers resolved, while preserving separate AP access items for individual story
sequences. Abilities and character ownership remain controlled by AP. No world/save
changes or story trigger patches are implemented by this research.

## Two mapped entry points

| Sequence | Script / native trigger | Completion evidence | Independent effects |
|---|---|---|---|
| Duke grappling-gun meeting | `get_grapple_gun/goto_forest.sf`, `Story_A1_M5_S1_MeetSheriff`, backup `Story_A1_M5_S1_MeetSheriff_Backup` | `Flow_Setup.Flow_Completed.Act_1_GetGrappleGun` | GrappleGun ability and item creation for both players; dialogue stage 6; transition to Act1 mission 6; commit and autosave |
| Natalia roadblock/bridge scene | `road_block_removal/road_block_removal.sf`, `Story_A1_M3_S1_Bridge`, ensure hotspot | `Flow_Setup.Flow_Completed.Act_1_RoadBlockRemoved` | Pedestrian blockers enabled; `RoadTraffic/GGBridge` traffic toggled; vehicle group 3 unlocked; resume cutscene `07_ImpossibleRescueA` and door `Flow_1.5_NatalyaChase`; Act1 mission 4 and autosave |

The bridge script's `GGBridge` resource associates it with the Golden Gate scene;
the player's localized bridge name has not been independently checked.

Duke's `ForestSetup` activates the story hotspot and accepts player entry, including
co-op player 2. `UnlockGrappleGun` grants both ability and actual tool. Disabling only
the popup or the completion bit cannot suppress that native reward. `StartNextMission`
also starts subsequent story progression; a free-order AP version must replace or
contain that transition rather than let it advance the global campaign cursor.

Both scripts disable their own story hotspot on job stop. A permanent AP entry must
therefore live independently of whether the vanilla mission job is currently running.
The backup/ensure entry paths need auditing too; gating just one visible icon is not
a complete access lock. No replay behavior has been verified in the running game.

## Automatic unlocks on load

Despite its debug directory name, `debuguse/unlocks/forceunlocks.sf` contains explicit
fresh-boot restoration branches using `Flow_Start`, `Flow_Act`, mission and stage.
Whether every branch is active in retail must still be verified; the static dependency
is sufficient to rule out assuming advanced story flags preserve AP locks.

In its Act1 branch, mission >4 unlocks SuperBuild and sets
`SuperBuild_Saves.WI_Farmlands.0708_VD.nState = 2`; mission >5 unlocks GrappleGun;
later branches restore other abilities, disguises, ferry/train states. It commits
abilities and clears `bFreshBoot`. Freeplay branches also grant abilities/classes.
Thus simply using a completed save or later campaign cursor risks granting AP items
and marking planned checks already completed. It must not be used as the bootstrap.

## Implementation boundary

Keep three distinct state domains:

1. A curated, versioned world-access bootstrap: remove only story barriers needed
   for exploration. Preserve unopened collectible/activity flags, unbuilt AP-relevant
   structures and item-controlled obstacles. Intro skipping must not pre-complete checks.
2. Seed/player/save-bound AP state: owned story-access items, received abilities and
   acknowledged checks. Bootstrap writes must never emit checks or create item grants.
3. A single active native story session: set up its local actors/resources and entry
   requirements, suppress native randomized rewards, emit its source check once, then
   return to the open city without enabling the next campaign mission automatically.

The proposed access items are progression if their sequences contain checks. Sequence
entry can additionally require relevant AP abilities when gameplay needs them. Duke's
grant scene must remain completable without already owning GrappleGun; any later
mandatory grappling segment must be separated or represented in logic to avoid a
self-lock. Item names/granularity and checks are not yet finalized.

Next technical validation: trace job start/stop and city restoration, identify the
smallest bootstrap writes, and test one contained Duke session in a separate test
slot/backup. Do not set every Flow_Completed or CityObjective bit to true. Native
game-thread control and immediate supported persistence are still prerequisites.

## Reproducible evidence

`tools/story_access_catalogue.py` generates an ignored file-local evidence index with
259 rows across the three scripts. It records source line numbers, hotspots and
potential effects; it is not a control-flow proof. `bridge/story_reader.py` now reads
the two named completion flags and `Flow_Saves.Act_1.Fix_Road_Block.RoadBlockFlowObjects`
with resource-hash/type validation. The read-only diagnostic artifact was rebuilt;
42 tests passed. Full-game open-city operation and scene replay remain untested.
