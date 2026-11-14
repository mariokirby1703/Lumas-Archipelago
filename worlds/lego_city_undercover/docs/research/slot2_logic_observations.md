# Slot 2: initial Auburn observations

The user confirmed the first cutscene could be skipped with N0CUT5 enabled from the main menu. The loaded native save was identified as slot2/game1.legocityundercoversavegamedata.

The following checks were reached without additional disguises, all in Auburn according to the user:

| AP location ID | Source | Reward |
| --- | --- | --- |
| 1104358288 | sf_docks_0715.giz:27:7, small Super Brick / Gold Plate | 1,000 Studs |
| 1580895997 | sf_docks_1018.giz:722:3, small Super Brick / Gold Plate | Jetpack |
| 1128381259 | DisguiseBooth_SF_DO_0918 | COLLECT_1-15_DEEPSEADIVER |

All three outgoing rows are acknowledged=1 in the new journal, and receipts 0, 1 and 2 are applied with native save verification. This is not a partially sent set of checks. These observations are recorded in notes/analysis/logic_observations.json. They are observations of no additional disguise requirement, not a claim that every other ability was absent; Jetpack had been received before the booth check.

Jetpack is already classification=progression in the generated item catalogue. User design correction: Astronaut should become a progressive item (first disguise, then Jetpack). The current separate native flag/item does not yet implement that progression. Complete access rules are not yet implemented.

The game source chars/collection.txt lists COLLECT_1-15_DEEPSEADIVER in category 8 (CATEGORY_SPECIAL01), whose parent is category 0 (CATEGORY_CIVILIAN). It is a civilian special character. The receipt is saved; actual booth visibility/selection for this model is still unresolved and must not be inferred from disk ownership.

Requested future area gates: Auburn is the start area; entering an unreceived district should return the player to the last allowed position. This is a requirement, not a currently implemented native feature. Resource names such as sf_docks are not a substitute for the map district. No automatic teleport or actor replacement was introduced here.

## Expanded civilian baseline

The user confirmed all checks reached so far were obtained without using Police or another additional disguise class, and reported Police as the next blocker on their current route. Journal inspection found 11 acknowledged AP location IDs and no received Police-class item. This is not proof that every civilian-accessible check on the whole map has been exhausted. Additional AP skins/Jetpack had already been received, so the observation concerns used classes, not an empty item inventory.

The complete acknowledged set is captured in notes/analysis/logic_observations.json. The two Police source entries (story_disguise:COP and the garage cop token) may represent duplicate detection of the same unlock; do not count them as two independent starting opportunities without resolving that overlap. The toy-car ride was also completed class-free according to the user's play sequence, but is not an active location in this running seed.

Future generation must make enough genuinely reachable starting checks available to obtain Police before Police-dependent story and exploration routes are required. Current create_regions still places all locations in one freely reachable experimental region, so this test seed is not logically guaranteed completable. For a deliberate next test step, AP's item-cheat command can grant Ability: Police through the normal receipt pipeline when enabled on the test server; no server command was sent or character granted during this investigation.
