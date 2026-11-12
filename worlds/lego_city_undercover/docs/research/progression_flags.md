# Progression flags

Confirmed symbolic script references in GAME4.DAT:
`jobs/scripts/debuguse/unlocks/forceunlocks.sf` reads `Flow_Setup.Flow_Act`,
`Flow_Start`, and Act1 through Act4 mission/stage values via Job.GetValue.
The script grants class and ability unlocks according to these values.
It is a debug-use script; its existence does not prove it executes during normal gameplay.

Examples of script-level operations include UnlockAbility(grapplegun), UnlockAbility(scanner),
UnlockAbility(Jetpack), UnlockCharacterDebug(cop/robber/miner/astronaut),
CityObjective_IsComplete and CityObjective_SetComplete.
These names are static evidence of engine mechanisms, not safe callable APIs from Python.

The same script updates train-station jobs and city-objective completion together. This demonstrates why changing
one completion bit in isolation may produce inconsistent saves or rewards.
The normal Act 2 police-station script also calls UnlockAbility(Act2), updates Act2_Stage,
and uses PushExtraCharUnlockWithDisguiseSequence. Ability gating must reconcile normal story grants.

No independently disabled ability or randomized class has been live verified. Civilian/Police starting behavior,
softlock prevention, final-goal flags and Free Play transition rules remain unresolved.

## Live Police character unlock observation

In save slot 1 the user reported the notification Freigeschaltet: Chase McCain (Polizist).
The snapshot live_police_uniform_unlocked.json showed no changes in either 51-byte ability array
or the unambiguous objective completion records compared to the preceding station snapshot.
This character notification is therefore not currently detected by the ability-table reader.
A separate character/class state mapping is required; the exact notification/animation capture timing
and persistent character flag remain unverified. No received-item grant was performed.

## Central computer live transition

In slot 1, after the user reported activating the central computer, the Map ability query changed
from false to true compared with live_police_field_activated.json. Other queried abilities and unambiguous
objective bits did not change. The user reported 14:07 playtime and 1 percent completion; these screen counters
were not independently read. Evidence: notes/analysis/live_central_computer_activated.json and its observation file.
This is an observed progression-correlated query transition, not proof of item granting or restart persistence.

## Detective-mode notification

After the user reported unlocking detective scan in slot 1, live_detective_scan_unlocked.json showed
no change in the 51 queried ability states. Source jobs/scripts/lcpd/lcpd_lobbysecond.sf:1106 invokes
UnlockSequenceAndAnim(MechIcon_DetectiveMode, ABILITY_DETECTIVE_MODE), not UnlockAbility at that point.
The following states explicitly start the Detective_Spot job and check the DetectiveMove character context.
This notification must not be equated with the separate Scanner symbol in the global ability table.
LockAbility exists statically, but its effectiveness for this detective context is unverified. No lock/write was attempted.

## Requested fine-grained interaction gating and office-key observation

The user requests independently gated pig riding, optionally per map district, in addition to class/ability items.
This is a design requirement under investigation, not implemented support. The global ability symbol table
contains Pigs, but no correspondence to the mount interaction or district-specific behavior is verified.
Story pig objectives and open-world pig-return activities must be distinguished.

Slot 1 live_chief_office_key_held.json was captured after the user reported carrying the chief-office key.
The current reader has no held-object field. In lcpd_lobbysecond.sf, WaitForChiefLock references
Story_02_LobbyLock and activates it following the key-found conversation. ChiefAwakesMinicut later references
M02_Dspot_key_item and deactivates/hides it. This connects key-related story state and lock setup,
not a persistent key-inventory flag. A randomized key item/check needs verified acquisition/consumption,
checkpoint restoration and save/reload behavior; no such implementation or write was attempted.

## First robber: live completion transition (2026-11-12)

After the user reported the first successful robber arrest in slot 1, Flow_Setup.Flow_Completed.
Act_1_CatchRobber_1 changed false->true. CatchRobber_2 and CatchRobber_3 remained false.
Act1_Stage changed 1->3 and DialogueStoryStage 1->3. Evidence: live_before_first_robber.json
and live_first_robber_arrested.json. This establishes an individually observed completion candidate,
not AP transmission, randomized rewards or restart persistence of this particular flag.

## Criminal scan live unlock (2026-11-12)

Following the user-reported criminal-scan unlock, live_criminal_scan_unlocked.json showed the Scanner
query changing false->true compared with live_first_robber_arrested.json. Selected story values did not
change. This differs from the earlier detective-mode popup, which did not alter the 51-entry table.
It is a live-correlated unlock mapping, not proof of safe locking, AP granting or save persistence.

## Second robber and garden valve (2026-11-12)

The garden valve appeared as attached definition #ex_192_Valve_Handle_item while context remained Default;
it disappeared after the user inserted it. Captures: live_second_robber_valve_held.json and
live_second_robber_valve_inserted.json. The generated #ex prefix is not a stable AP location identifier.
After the next reported arrest, live_second_robber_arrested.json showed Act_1_CatchRobber_2 false->true,
with CatchRobber_1 still true and CatchRobber_3 still false. This independently distinguishes the second
completion. No AP check was transmitted and no reward was modified.

## First booth completion (2026-11-12)

The first observed city-objective completion transition was DisguiseBooth_SF_DO_0918,
FNV-1 hash 2104704297, runtime bit index 321, changing false->true. Scanner data classifies it
as DisguiseBooth in internal district SF_Docks; the user identifies the displayed district as Auburn.
The mechanic token-found state and Gold Brick count also changed in that observation interval.
These correlated rewards must not be assumed to be independent physical pickups. No AP checks were sent.
