# Police wardrobe skipped by an early AP Police grant

## Cause

The original garage WaitForToken state tests CharacterAvailable("Cop") and
Ilocker_Buildit_01.GetOutput(0). AP can satisfy the first condition before the
wardrobe is used. Building it then advances the story, bypassing the native COP
and linked Grace discovery events. The later tutorial no longer exposes the
first-use wardrobe interaction.

The old catalogue also assigned two IDs to COP discovery: story_disguise:COP and
the wardrobe source pickup. It contained no independent COP_FEMALE_P2/Grace source.
The roster identifies COP_FEMALE_P2 as the linked cop reward, and earlier native
observations recorded it in the extra-grant queue alongside COP.

## Recovery and future seeds

station_rewards.py recovers only those two specific station keys after a validated
read of PDA.acquired=true. The original script sets that flag at ActivateLiftDoors,
after the garage reward stage and keypad/Ellie sequence. Merely owning AP Police,
equipping it or entering/building the wardrobe is insufficient evidence.

client_checks merges the completed reward keys into normal offline reconciliation.
Only locations active in the connected seed are considered, and acknowledged checks
are excluded. No native ownership, discovery, pending-grant, story or save bits
are changed to manufacture a reward. Old seeds keep both IDs; future catalogues
use the second ID for Grace Makepiece (COP_FEMALE_P2), instead of another COP check.
The Grace check also accepts its genuine native discovery before the fallback.

## Current live repair

tools/recover_station_rewards.py defaults to inspection. --apply requires the loaded
native AP marker to match exactly one journal binding and the same proven tutorial
state, then enqueues only eligible active station checks through Journal.queue.
The ordinary running AP client sends/acknowledges them. It creates no second network
connection and never writes game memory or save files.

For seed 87147018255242826356, team 0, slot 1, the live reader confirmed PDA.acquired
and PDA.synchronised. Both missing checks, 1000355890 and 1481056630, were queued
and subsequently server-acknowledged. Evidence is in
build/lego_city_undercover/station_reward_recovery.json.

Four new tests cover pre-owned Police without false checks, completed-tutorial
recovery for old and new catalogues, separate Grace discovery, deduplication and
disabled location categories. The full run completed 269 tests, 261 passed and
eight environment-dependent tests skipped; no native/UI source was changed here.
