# Local ability testing: `/give` and `/remove`

This feature is for **Archipelago logic development**, not receipt injection.
It overlays real server-owned item counts in this Sonic Client process and
projects the result through the existing native movement, Wisp, Boost, capsule,
world-access and breathing permission paths. The host does not modify
`ReceivedItems`, item IDs, the seed's item pool, or the durable AP item journal.
All overrides disappear when the runtime is released or the client process exits.

The client must be connected to a verified Sonic Colours AP slot. Commands:

```text
/testitems list
/give Double Jump
/remove Double Jump
/give White Boost Wisp
/remove White Boost Wisp
/give Cyan Laser Wisp
/give Stomp
/give Rail Switch
/remove Rail Switch
/give Rail Jump
/remove Rail Jump
/give stunts 1              # Good
/give stunts 2              # Great
/give stunts 3              # Awesome
/give stunts 4              # Outstanding
/give stunts 5              # Amazing
/remove stunts all
/give Assist Change
/remove Assist Change
/give Drift
/remove Drift
/give Swim
/remove Swim
/give Progressive Crouch 2
/remove Progressive Crouch all
/give Progressive Breathing 5
/remove Progressive Breathing 3
/give legacy breath         # legacy 30-second breathing item
/give Progressive Game Land Speed 4
/give wisps                 # all eight Wisps, including White Boost
/remove wisps               # temporarily lock every Wisp
/give movements             # all Movement abilities, maximum progressive levels
/remove movements           # lock all Movements, including legacy Breath
/give all wisps             # alias of /give wisps
/give all movements         # alias of /give movements
/give all                   # maximum of every movement/Wisp ability
/remove all                 # effective 0 for all movement/Wisp abilities
/testitems                  # current local overrides, actual vs effective
/testitems reset            # clear every local override
/sonicmovement              # permissions/owned_mask reflect overrides
/sonicstatus                # real server ownership + effective inventory
```

Names and shorthands are case-insensitive. On progressive abilities,
`/give ITEM N` sets exactly tier N, while `/remove ITEM N` subtracts N tiers.
The trailing `all` selects maximum/zero respectively.
`/remove` can temporarily suppress items genuinely received from AP.
`/give ITEM N` sets the desired tier again; `reset` restores the
real AP inventory. The commands reject filler, traps and consumable Boost refills;
manual refill delivery would bypass important receipt-specific accounting.

**Important:** While local test permissions are active, physical checks that
you genuinely complete can still be transmitted to the AP server! Use a throwaway
seed / backup save for logic testing. Giving a test ability does *not* forge a
LocationCheck or a ReceivedItems packet; synthetic Emerald ownership alone is
explicitly prohibited from completing a Super Sonic inventory goal. Native map
or Wisp visuals may require a scene transition to refresh after a removal. An
override never bypasses the client's PAL, Dolphin instance or save-binding
write guards.


## Short Wisp capability names and progressive tiers

All Wisp colours and powers are accepted, e.g. `/give laser`, `/remove drill`,
`/give rocket`, `/give cube`, `/give hover`, `/give spikes`,
`/give frenzy`, `/give boost`. Full names still work.

`/give breath N` maps to **Progressive Breathing** (not retired `Breath`) and
sets the **absolute** tier, rather than granting N additional tiers.
`/give breath 2` therefore means 10 seconds, even when an AP history already
contains more Progressive Breathing items. Levels are 0/5/10/20/40/60 sec for
tiers 0/1/2/3/4/5. To set 0, use `/remove breath all`.
`/remove breath 2` subtracts two tiers from the effective total.
For the old fixed 30-second item use `/give legacy breath`.

Other progressive permissions (Crouch, Game Land Speed) also interpret
`/give ITEM N` as the target tier; `/remove ITEM N` subtracts N tiers.
The actual AP item history is never changed by these commands.

## Bulk Wisp and Movement groups

`/give wisps` and `/remove wisps` modify just the eight Wisps.
`/give movements` and `/remove movements` modify Wall Jump, Homing Attack,
Mid-Air Boost, Double Jump, Stomp, Swim, Progressive Crouch (tier 2),
and Progressive Breathing (tier 5, 60 seconds). The retired `Breath` permission
is masked by both movement batch actions to prevent its old timer from
overriding progressive tiers. `wisp(s)`, `movement(s)`, `moves`,
`all wisps`, and `all movements` are accepted as group names.
These are still local session overlays, not actual AP item deliveries.


## World access and shortcuts

The five *unlockable* story worlds are controlled by their AP `Shuttle`
items. World names are case-insensitive and may be shortened to their first
word. Both individual commands and an all-world group are supported:

```text
/give sweet                 # Sweet Mountain Shuttle
/remove sweet
/give starlight             # Starlight Carnival Shuttle
/give planet                # Planet Wisp Shuttle
/give aquarium              # Aquarium Park Shuttle
/remove aquarium
/give asteroid              # Asteroid Coaster Shuttle
/give world sweet           # equivalent to /give sweet
/give Sweet Mountain        # full world name, Shuttle suffix optional
/give worlds                # all five unlockable World Shuttles
/remove worlds              # temporarily mask all five
/give all worlds            # equivalent to /give worlds
/testitems reset            # restore real AP World Shuttle ownership
```

The client projects the **effective** local Shuttle counts through its
existing world-access rules, without sending AP receipts or modifying the
seed. A map screen may need to be exited and re-entered for cached UI to
refresh. `Tropical Resort` is the always-available starting world in the
native gate, so it cannot be locked by a Shuttle override and is deliberately
not included in `/give worlds` or `/remove worlds`. `Terminal Velocity` has
no Shuttle item; its existing access requirement is ownership of all eight
Wisps. Use `/give wisps` and `/remove wisps` to test that gate.

Drift is an independent progression item (ID 847000046), included when movement unlocks are enabled. PAL native request 38 is denied without it. Restart the Act before testing; an already active drift is not forcibly interrupted. Old seeds can test with `/give Drift`. Both the APWorld and complete Movement Gecko profile must be updated together because the compact native permission layout changed.

Denied Drift (38) and Slide (41) requests now route to native exit 3 instead of retaining a forbidden predecessor. This uses the native transition callbacks (original exits at 801505C0 and 80159A70), without host edits to player state or animation fields. Requires the updated complete Movement Gecko profile; live validation pending.

Progressive Stunts (847000048, five pool copies) gates only TrickJump stunt performance/animation/reward routine 80148454. Ramp launch, State 46 flight and normal landing remain native. Included in Movement Unlocks; Off grants the native routine. Update complete Gecko profile and APWorld together. Live validation pending.

Progressive Stunts grants a maximum of 0/1/2/3/4/5 stunt performances per ramp flight. Quality order: Good, Great, Awesome, Outstanding, Amazing. The original ramp-specific native maximum still applies. Existing seed item ID 847000048 now grants one progressive tier.

A fresh verified Act-1 prologue can rebase an unbound journal after reconnecting or abandoning an unfinished intro in the same authenticated AP seed. Prior prologue evidence is archived and AP receipts/checks preserved. Loaded foreign saves and incomplete freshness evidence remain blocked.

Rail Jump (847000049) gates native GrindJumpShort state 29. Rail Switch (847000050) independently gates GrindJumpSide state 30. Same-seed fresh games restore physical Red Rings from explicitly archived seed playthrough/prologue epochs as well as the current epoch. AP Red Ring counter receipts never manufacture physical collections.

Directional Rail Jump requests (29) additionally require Rail Switch when native held input actions 2/3 are set. The native mask is read from the current actor at request time. Straight jumps require only Rail Jump; explicit GrindJumpSide (30) requires only Rail Switch. CR0 is recomputed by the immediately following native cmpw at 80033890; the gate modifies no other CR field and restores LR/GPRs.

# Skydiving

`/give Skydiving` enables the native Diving glide. `/remove Skydiving all`
restores the lock. Without the item, every PAL `CStateDiving` update requests
native `CStateFall` (15), including a glide already in progress. The native
dispatcher performs state cleanup; no host writes alter velocity or state IDs.
Install the current complete movement Gecko profile and APWorld, then restart
client and emulation. Existing seeds can test the item locally; new seeds
include one progression item when Movement Unlocks is enabled.

Movement masks and Skydiving permission now preload on verified bound world
maps and Game Land selection, without requiring a live Sonic actor. The guest
gate validates the next native actor/machine/reverse link on its first request.
ReceivedItems and local give/remove/reset also publish idempotent movement
permissions immediately when the current scene permits verified writes.
Unavailable/loading or unbound saves defer to the regular poll; no filler is
replayed by this event path.

`/give Quick Step` enables QuickStep (native state 48); `/remove Quick Step all`
locks it. Item ID 847000052, permission bit 11, one progression copy in new
Movement Unlocks seeds. Denied requests use native Run (3), the same exit
requested at 80194070. Normal section travel does not require the item. The
current full Gecko profile is required; older masks are recognized for PAL
verification but are not overwritten with unsupported new permission bits.

Check scanning now captures pickup/result evidence and exposes a transport
checkpoint before slow permission projection. The async client sends the
durable queue and processes server acknowledgements at that checkpoint.
Result coherence compares authoritative state/score/grade/time fields while
ignoring unrelated live UI animation values.

Consumable settlement accepts a late observation after a slow poll. An exit
does not undo already completed, individually guarded native writes/readbacks.
Such receipts remain confirmed without replay; HUD appearance is still separate.
Historical settlement-only errors may be reconciled when every recorded write
completed. Partial writes, missing completion evidence and interrupted native
attempts remain uncertain and are never automatically replayed.
