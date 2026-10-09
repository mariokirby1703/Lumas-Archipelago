# Gameplay and YAML overhaul — schema 3

## Implemented code

- Automatic fresh New Game detection and immediate Red Ring, capsule and completed
  result Clear/Rank checks remain active during the unsaved mandatory intro.
  Durable journals, RoomInfo-authenticated transport and genuine ACK handling
  retain their existing protections.
- Capsule refresh follows the available native constructor sequence: model
  `800D3EB4`, interaction/collision initializer `800D3FF8`, default-state
  transition `800D5490`, visibility/movement `800D4298`. It also repairs a
  previously visually-refreshed actor whose `+B4` collision handle is null.
  Opened `+110` is preserved. The `+149` variant is no longer blanket-excluded;
  it retains its native colour and eligibility. `+148`/`+14A` force special
  colour 7 in the original constructor and remain outside this coloured hook.
- A separate Gecko hook intercepts native flag setter `8015ECC0`. For the
  authenticated selected/intro flag buffer, World bits 20..26 and coloured-Wisp/
  Super bits 0..7 use AP ownership. Other flags retain their vanilla operation.
  It records seven coloured discovery transitions and 21 Game Land clear
  transitions without granting the corresponding AP items. Hook data includes a seed identity tag. On a seed change the
  client disables the owner, zeroes only the hook event words, verifies the
  reset, and activates the new tag/owner. Snapshots reject another seed's tag;
  old events cannot become new-seed checks, and reused event bits remain usable.
- World/first-Act permission projection revokes unowned World flags and first-Act
  availability, refreshes observed map caches, and preserves C-bank clears and
  ranks. Starting-stage A-bank path availability applies after first save and
  includes eligible bosses/Terminal Velocity without fabricated clears.
- Schema 3 removes optional AP Wisp/World/Emerald modes and the bundle strategy.
  All eight Wisps, nonstarting World Access and seven colour-named Emeralds are
  always progression. Numeric IDs are retained. Five goals use native clears,
  cumulative physical pickup identities, or all seven AP Emerald items.
- Ring packing computes `T=ceil(4R/3)`, maximizes singles fitting non-excluded
  progression capacity, and uses exact-value +5/+10 bundles when required.
  Precollected progression reduces the remaining pool. Small access pools are
  placed early so a large singles pool cannot consume their accessible sphere.
- Wisp Capsules is one boolean with 680 eligible distinct story/Game Land
  instances. Capsule rules require their corresponding item rather than all
  Wisps. Seven discovery locations follow the native discovery table at
  `80720B98`, queried by `80228B30`; they are attached to the corresponding
  stage regions and use clear-route logic.
- Music Off/per_world/anywhere writes the original normal-Act mission table's
  inline cue strings at a stable attributed map. All 36 mission identities,
  vtable, vector bounds, cue whitelist and ownership are checked before writes;
  each write is read back. Off restores vanilla after a prior shuffle.
  No manual CPK replacement is required for this path.
- English options/groups/examples, a non-destructive YAML migration command,
  schema migration rejection, updated setup and loaded-code hashing include
  the new runtime implementations.

## Native evidence and save-index 03

The original constructor proves that changing the model alone omits collision
creation. `800D3FF8` creates native collision handles at actor `+B4` and,
conditionally, `+B8`; the code calls it only when `+B4` is null, rather than
rebuilding an already-present interaction. This is static PAL evidence, not
an observed successful collision in Dolphin.

The save-index byte is not merely a count in the accessor: `8015FA18` reads it
and directly selects `container+8+index*19608`. `8015F998` writes that byte.
The save menu supplies its selected-row field `+94` to this setter at
`8023EB30`, `8023EE9C` and `8023F104`, and restores its prior selection from
`+98` at `8023ECD8`/`8023F214`. Initialization allocates six internal records;
this alone does not establish six visible user slots. Native New Game also
initializes an explicitly selected internal record at `8016D860`/`8016D880`.
Thus 03 selects an internal record when used by the accessor; its exact
intro/default/UI-copy role is not fully proven. The client has not expanded
persistent user-slot acceptance based on this byte. Bounded intro observations
can read that record without treating it as a fourth visible save, and independent
scene/mission/New Game detection does not require a persistent selected slot.

## What was validated

This change has no new live Dolphin gameplay verification. The read-only DME
probe found no running emulation. Existing user-reported successful checks are
preserved but are not new validations of this build.

Offline validation includes original PAL executable disassembly, original RAM
capture readers, write overlays at real native addresses, emitted PPC execution,
exact hook and write-policy rejection tests, real restrictive generation/fill
and the local CommonClient WebSocket protocol/ACK regression. Capsule native
functions are explicitly stubbed in the PPC interpreter; render, allocator and
collision behavior require the real engine.

## Exact remaining validation and implementation gaps

- Verify Cyan collection/collision after receiving its Wisp mid-Act, including
  repair of a capsule refreshed by the old visual-only hook.
- Verify Orange Rocket in Planet Wisp Act 1 and identify its current actor's
  subtype/eligibility from the two newly mentioned capture pairs. Those pairs
  were not located during this turn; the available October 9 pairs predate
  this collision repair.
- Verify a boss cannot grant an unowned World or update an unobserved native
  waypoint cache outside the implemented accessor/cache paths.
- Verify audible shuffled music on next load and after reconnect/Off restoration.
- Verify all seven AP Emeralds expose and permit native Super Sonic; the bit
  write has guarded offline readback but no new complete native playthrough.
- Emerald checks observe a real native Game Land clear transition and require
  all three native clears. A distinct per-group Emerald reward-presentation
  event has not been identified; this is not claimed as that event.
- White Boost scripted/player grants and White's first-discovery event remain
  unresolved. White's stable discovery ID is retained but not generated.
- Native DeathLink/Swim and level randomization remain unsupported and reject
  non-Off generation. Unknown physical-ring routes conservatively require all
  Wisps; provisional clear routes still need a complete gameplay audit.

Use [setup](setup_en.md) for a new schema-3 server and both updated Gecko codes.
