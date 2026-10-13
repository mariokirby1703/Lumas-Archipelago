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
