# October 10 remaining-requirements patch

## Production changes

The previous hook at `0x801014E0` intercepted the native coloured-Wisp
availability query. Index zero is Yellow Drill, not White Boost. Its current
payload is inert, and the client also clears the lock word in the exact known
previous payload. No held-Wisp, scripted capsule-enable or opened-actor fields
are written.

White Boost Lock now gates ordinary Boost query/use outputs at `0x8020E208`
and `0x800CD730`, and native pickup/script additions at `0x80101510`. Locked
additions preserve the previous gauge. The native Super provider bypasses the
ordinary query and addition path. Off executes the displaced instructions.
Install the updated `data/SNCP8P_capsule_refresh.ini`; restarting only the client
can neutralize the old coloured gate, but cannot install the new White gates.
Exact historical payloads remain accepted; arbitrary replacement code does not.

World/Wisp blanket early placement and the restrictive fill hook are removed.
One random ordinary World Access remains early to expand initial capacity.
World Access and Wisps cannot be placed behind Game Land stages 2/3, whose AP
Ring dependencies could otherwise form indirect locks. Large Singles pools
reserve Clear capacity for other progression when the other locations can hold
the entire Ring pool. All eight Wisps remain ordinary shuffled progression.
The 100-seed regression checks reachability, completion, varied placements and
varied Wisp spheres, with no early Wisps.

Story/Game Land synthetic Clear events are removed. Logical completion uses
region reachability and requirements; runtime victory still requires observed
native completion. Clear, Rank, pickup and Emerald server location IDs remain.
AP counter items are now `Red Ring`, `5 Red Rings`, `10 Red Rings`, with their
existing numeric IDs and unchanged 4/3 buffer and packing behavior.

## Evidence boundaries

The original notes/mem1.raw and mem2.raw captures and PAL executable were read.
The new native hook tests execute emitted PPC, verify original PAL text hashes
with only exact known hooks normalized, check caller register preservation,
profile isolation, unlocked behavior and previous payload compatibility.
These are offline tests, not in-game execution of the new hooks.

A read-only Dolphin observation during this session found Aquarium Park Act 1
with permissions 0x41, and a later observation found Sweet Mountain Act 1,
permissions 0x41 and held native Wisp type zero (Yellow Drill). No trap or memory
write was performed by these observations. Neither proves the new code ran.
The user's earlier acknowledged Red Ring test belongs to the previous build.

## Still unimplemented

Starting Act is not yet merged into Level Randomization; native shuffle remains
disabled. `0x8016DF20` is a candidate mission-name dispatch site, but changing
only that operand does not establish the required intro/save/results ownership
contract. Native ranks/clears continue to use the physical slot index while
pickups use the loaded mission. A production shuffle needs that separation in
save attribution, results reconciliation and restart recovery before activation.
No table/name-only mutation is presented as a working stage shuffle.

Music randomization still covers the established normal-Act cue table after
intro. No common BGM-only dispatch hook with verified title/menu/map/result
coverage and pre-playback seed setup has been established. Voices/SE and
original game files are untouched. All-game music is not claimed implemented.

The underwater observation does not identify a reversible native swimming
state transition or timer restoration contract. Swimming traps remain disabled.
The new White gates, actual colour pickup with Boost Lock enabled, all Super
paths and complete playthrough still require live testing with the updated
Gecko code. Existing Starting Act/Terminal Velocity exceptions are unchanged,
so the requested strict merged-option Terminal Velocity behavior is also pending.
