# Train, tram, passenger and T-Rex function review

Implementation update: [Disembark and creature return](disembark_and_creature_return.md) supersedes the unfinished-path status below. Passengers/rail use a separate foot anchor and original ClearVehicle; ridden creatures use a reviewed GetRidden target and character teleport. Live behavior remains unverified.

15 November 2026, pinned Steam DX11 executable. This supersedes the previous blanket exclusion of RideAlong from boundary commands. It does not assert that rail consists or creature takeovers are fully restored.

## Native rail calls

The script action Vehicle_AttachToSpline_YFree dispatches at RVA `0x118100`. It obtains the vehicle AI through `0x4a8970` (exact accessor: `return vehicle->field_378`), subtracts `0x10` to reach its owner, resolves the named world spline via `0x51cde0`, and invokes the AI virtual slot `+0xb8`. An empty spline name reaches the same slot with a null spline. This changes a real route controller; it is not just an animation label.

Vehicle_DisableManualAIControl at `0x118590` obtains that same owner and calls `0x1929a0`. That body accesses the vehicle through AI owner `+0x38`, clears vehicle flag `+0xfc8` bit 1, and sets it according to the inverted boolean. Its script name should not be interpreted as a permission to freeze the whole mission.

Vehicle_ConnectRailVehicles at `0x118220` resolves both vehicle AI owners and calls `0x192250`. Vehicle_ReleaseCarriage at `0x11a1a0` resolves the owner and calls `0x199b90`. The latter checks the live weak pair at owner `+0x11a8/+0x11b0`, adjusts link state `+0x11a4`, calls `0x194170` and releases the weak reference through `0x712410`. Raw copying of these links would bypass lifetime and physics operations.

`train_setup/train_control.sf` has separate WithPlayer and WithoutPlayer teleport states. The script tracks front engine, carriage and rear engine, their individual locators, occupied cars, line, direction and per-line spline limits. It releases links and spline attachment before relocating/recreating the train, then reattaches all cars and calls ConnectRailVehicles. A boundary checkpoint containing only the occupied vehicle's matrix is insufficient to reproduce this operation.

`sf_trams/sf_trams.sf` distinguishes driver, Passenger1 and other passengers. Its UpdateAutoTram, UpdatePlayerTram and SwitchTramDirection states control a CityTramSpline-bound Courser. Driver/passenger transitions and autonomous route movement must be considered together; changing one world transform does not restore spline progress.

## Passenger handling implemented

Boundary opcodes 21/22 now accept RideAlong (11) as a candidate in addition to Default (46) and RideObject (157). The native body still requires a live mounted ApiVehicle weak reference, reviewed transform getter, matching actor/vehicle/binding, valid city scene and nearby checkpoint. RideAlong without a vehicle returns busy before any mutation. It does not teleport a scripted character as though it were a car. Synthetic tests cover both rejection without a vehicle and a mounted passenger return through the physics vehicle path.

Other scripted contexts, including DropPoint, takeover transitions, cargo and cinematics, remain explicit deferred diagnostics rather than silently being treated as ordinary driving. Their context and actual vehicle class appear in the copied area report. No context/state bytes are forced to Default. RideAlong permission does not itself prove a train or tram's route is restored.

## T-Rex

`GAME4/jobs/scripts/act_3/trex_chase/trex_chase.sf` declares cDino as Character and creates `CreateAICharacter("Behemoth", "RideableCreature", ...)`. It invokes `ManageTakeover(Character=cPlayer1, TakeOver=cDino, #Instant, #LockedIn)` and contains an independent second-player dinosaur. This is a creature-character takeover, not ApiVehicle or the DinosaurSuitMan skin.

The script's reset sequence around lines 694-798 stores a reset position/direction, applies an AI override, clears an actual vehicle if present, restores takeover when necessary, and teleports cActiveDino. If missing, it recreates Behemoth and re-establishes takeover before restoring AI and navigation. Moving only Chase could leave the controlled creature behind or conflict with LockedIn. The new diagnostic recognizes an exact Behemoth actor name; it does not claim to resolve the creature solely from MindControl context.

Creature rollback still requires native takeover-target identity/lifetime and a checkpoint for that target plus rider relation. Rail rollback still requires the actual consist and spline state. No unreviewed calls, forced script stages, arbitrary pointer links or blind dismounts were added.

## Validation

347 unittest executions passed after passenger changes, including the native mounted-passenger/no-vehicle fixture. The DLL must be rebuilt and game/client restarted for new native eligibility. Rail, scripted transitions and T-Rex movement still need their additional native binding work and live tests; these are not reported as working.
