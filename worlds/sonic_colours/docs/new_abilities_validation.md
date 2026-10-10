# New abilities / Egg Medals patch: production and validation

PAL SNCP8P revision 0. Slot schema 5; generate a new seed. Existing numeric IDs
remain, except the retired Terminal Velocity Access ID (847000006) is absent.
Other items are not renumbered. New Egg Medal IDs are 847005000–847005020.
Old seed journals are retained, with the authenticated server seed/team/slot
and slot-data digest preventing reuse by the new schema/seed.

## Implemented

* Egg Medal Sanity defaults Off. On adds 21 original Game Land object checks.
  The original CPK ORC records were independently decoded and all 21 object IDs,
  instance indices and coordinates compared to the supplied CSV. Every object
  has its own native mission, location and immutable identity.
* Native class 0x8077E714 is the EggmanMedal actor. The Game Land pickup routine
  0x802F26BC emits its pickup effect, awards the bonus and at 0x802F27C4 proceeds
  to hide/remove that actor. The new exact Gecko C2 hook captures this event.
  The client arms only the actor validated through its stage manager, actor ID,
  wrapper, instance descriptor and original ORC position in a bound save.
  The thunk independently checks the armed actor, class, profile, manager,
  wrapper, record and instance. No host actor mutation, disappearance or score
  delta awards a check. A 21-bit native latch spans stage exit and host reconnect;
  captured events are copied into the existing atomic durable pickup journal and
  ordinary AP transmission/acknowledgement path. Captures predating seed arming
  are not imported. Journals deduplicate replays, deaths, reloads and reconnects.
* Egg locations inherit their actual Game Land AP Ring gate. Traversal rules
  conservatively require all eight Wisps because ORC placement alone does not
  establish an ability-free route. This is explicit conservative logic, not a
  claim of individual route validation.
* White capsules use signed native type -1, separately from Yellow Drill type 0.
  The updated capsule thunk has guarded owner/index/White-permission data.
  Locked unopened White uses the real ghost model and ghost lifecycle; ghost
  entry 0x800D557C calls collision/interaction disabling through 0x800D517C.
  Receipt of White changes the thunk permission, and native per-frame update
  uses content model, collision repair and real state-entry routines without a
  level reload. Opened actors and original ORC/script flags are untouched.
  Boost Lock Off grants White permission and leaves already valid White alone.
  Known older capsule hooks still permit core operation but do not provide this
  new White path; update the Gecko code. Special multi/alternate capsule forms
  (+0x148/+0x14A) retain their separate native contracts and are not reconstructed.
* Half Boost Refill no longer waits for White ownership. It directly adds half
  the native maximum to the safe living actor's gauge, capped at the maximum.
  Results defer to the next stage epoch. The durable receipt state machine and
  readback settlement remain; /sonicitems shows their confirmed/uncertain state.
  Filler never changes the separate native ordinary Boost-use permission.
* Terminal Velocity has no shuffled Access item or starting-stage exception.
  Its region and all three native entry bits require all eight Wisps. The native
  progression hook suppresses vanilla grants before that condition, and host
  guarded projection sets world bit 26 and stage/map caches when it becomes
  true. It does not complete the goal. Final Boss still requires both stg790 and
  the subsequent stg720 escape. TV cannot be selected as Starting Act; actual
  stage shuffling remains disabled, with TV excluded from permutation planning.

## Evidence

The four new original White captures were read. stg110 actor 0x90B59840, ORC
164/1, changes opened 0 to 1 and model state 1 to 5, while gauge stays 0 at both
captures. Instance 164/0 stays unopened. Those dumps reproduce the reported
failure; they do not show execution of the new White hook. The normal resource
constructor branches explicitly on ghost/content model mode, and the native
White content path retains subtype -1. No snapshot-specific address is used by
production writers.

A live read in this session identified Tropical Resort Act 3 (stg120), a stable
normal player, its gauge/counter addresses and native permissions zero. No
Dolphin write or new hook execution occurred in that observation. Existing
installed hooks remain recognized. Tests over emitted PPC and original memory
are offline evidence only. A real local WebSocket server acknowledges the
captured Egg Medal without ReceivedItems history; guest pickup execution in
that protocol test is simulated.

Tests cover 21 original ORC entries, native PPC event capture and ABI, exact
payload verification, foreign-profile/seed isolation, durable pickup/restart
and stage-exit replay, White ghost/unlock control flow, opened preservation,
White control allowlists, original White before/after reads, filler without
White, native TV projection, retired IDs, actual APWorld ZIP import and 100
varied Medal/Boost/Ring/Rank/goal seeds. Existing core tests remain in the suite.

Final complete suite: 879 passed (519.97 seconds), including the packaged ZIP
import and real local server acknowledgement test. All of these are offline
checks; no new Gecko payload ran in Dolphin during this session.

## Still not shipped

Story Speed Sanity and movement_unlocks are not exposed as active options or
items. 0x8026FF40/0x8026FF68 only read/write a discrete speed-selection field;
that does not establish a normal Sonic velocity cap. Normal running and scripted
running are distinct native states, but their common target-speed/physics paths
have not been isolated safely across rails, dash panels, springs, boost, camera
sequences, bosses and Super. The CStateRun name getter at 0x80069314, Homing
Attack name getter at 0x80099E78 and Double Jump name getter at 0x80099EA8 are
metadata accessors, not verified transition gates. Blocking these getters or
shared button inputs would not implement an ability unlock and could softlock
mandatory traversal. No fake gate or reused Game Land cap is shipped.

Live validations still required with a fresh schema-5 seed and all four updated
Gecko codes: actual Egg Medal pickups in two Game Land stages through server
acknowledgement and death/reconnect; White locked appearance and disabled
interaction, mid-Act unlock and actual native gauge grant; Half Refill visible
without White while use remains blocked; eighth-Wisp TV map path through
save/reload, and final boss/escape completion. Every normal movement and Super
mode must be exercised before claims of full behavior. Story speed/ability
work additionally needs a verified native setter/entry path and traversal logic;
it is unimplemented, not merely awaiting a final gameplay smoke test.
