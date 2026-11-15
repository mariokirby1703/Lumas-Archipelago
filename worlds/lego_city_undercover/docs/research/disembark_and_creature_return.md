# Disembark and creature boundary return

15 November 2026. This supersedes earlier reports describing rail and ridden-character return as unimplemented. The new paths are implemented and synthetically tested, but not visually confirmed in live gameplay.

## Trains, trams and passengers

The user explicitly requested returning Chase alone, leaving the transport behind. The bridge now retains a separate native foot checkpoint when capturing an allowed Default/unmounted state. Capturing a subsequent vehicle checkpoint does not replace that foot pose.

The reader follows the reviewed Vehicle_GetDriver action (`0x1194a0` -> `0x4b8450(vehicle,1)`): a bounded occupant list at vehicle `+0x580`, seat type `+0x3c`, occupied flag `+0x3d`, character interface `+0x20`. The host selects disembark for actual passengers or RideAlong, not just a cosmetic model name. It additionally recognizes rail models through Vehicle_GetModelName (`0x1193d0` -> `0x45d2c0`): vehicle `+0x358` -> `+0x58` -> `+0x48` -> `+0x20` string. Native script rail names are Courser, Cydonia, CydoniaCarriage, CydoniaRear, EmeraldNight_Cab, EmeraldNight_Carriage1 and EmeraldNight_Carriage2. This includes a player-driven tram.

Opcode 23 validates the same actor, AP binding, profile, world, current city district, original function signatures and separate foot checkpoint before requesting an exit. It calls the original Character_ClearVehicle script body (`0x1105d0`) with the character interface. This dispatches through actor `+0x340`, virtual `+0x220`; no weak pointers, seat lists or context bytes are manually overwritten. The native bridge issues that exit once and waits for a fresh unmounted Default state. Only then does it call original character teleport (`0x6709f0`) to the foot checkpoint. Vehicle transforms, train links, spline controllers and story flags are untouched. Unknown RPC outcomes remain latched; exit is not blindly resent.

The checkpoint must exist before boarding and be within 90 metres. Starting inside a forbidden area or long-distance fast travel is not covered by this nearby-boundary mechanism. An engine refusal to leave a locked/scripted seat can still require additional live investigation. There is no forced mission cancellation.

## Pig and T-Rex

`tile_pigcannons/pig_control.sf` creates `Pig` as `RideableCreature`, identifies its rider with GetRidden and teleports the pig before releasing takeover at the pigsty. `act_3/trex_chase/trex_chase.sf` creates `Behemoth` as `RideableCreature` and teleports the controlled dinosaur in its reset state. The shared boundary path therefore moves the ridden character with its rider relation intact rather than invoking a vehicle setter.

Character_GetRidden action `0x112ba0` first excludes a live vehicle weak reference, then follows actor `+0x340` -> controller `+0x88` -> virtual `+0x240`. The reviewed MechCharacterBaseInterface implementation at `0x1f8830` is exactly `return *(this+0x20)`. Both native capture and return require that exact implementation/signature, a valid city actor and the reviewed character transform getter. They re-resolve the actual target each time. The checkpoint pins target identity and movement kind; a different/dismounted creature cannot reuse it.

Boundary eligibility includes MindControl (152), BeenTakenOver (124) and RideObject (157), but these do not permit arbitrary character teleport: without a validated ridden target those contexts are rejected. The original character teleport moves the creature. No takeover target is invented or recreated, no rider relation is detached, and a creature is never passed to the vehicle teleport routine. Unreviewed accessor implementations remain unsupported rather than guessed. The new read-only `ridden` snapshot section exposes target/position and explicitly does not infer species from a context name.

## Validation and next native test

353 unittest executions passed. Native fixtures exercise a preserved foot checkpoint across vehicle capture, one-shot exit, later foot return, vehicle left behind, and ridden-target return across eligible contexts with the relation unchanged. Reader/host tests cover seven vehicle classes, no foot anchor, a player-driven tram and the exact ridden accessor. These synthetic fixtures establish control flow and guards, not successful physics or scripted seating in the retail game.

The game was unavailable for the final read-only probe. Rebuild and restart game/client, stand on allowed ground first, then board and cross a nearby forbidden boundary. Test each type independently; export area diagnostics at the first refusal. Long-distance fast travel, split-screen and forced seat locks still need dedicated handling/live validation.
