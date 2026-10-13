# Sonic Colours Wii PAL: schema 7 Movement / Swim / Breath research build

This is **not** a claim of a complete, live-validated movement randomizer.
The build adds the full requested item pool and records native state telemetry.
Do not treat receiving an item as proof its gate worked in Dolphin.

## Item catalog and permissions

| Name | Stable AP ID | Native restriction | Current status |
|---|---:|---|---|
| Wall Jump | 847000037 | request IDs 39 / 40 | experimental PPC only |
| Homing Attack | 847000038 | request ID 13 | experimental PPC only; in-flight captures sampled transition -1 -> 18 |
| Mid-Air Boost | 847000039 | request ID 9 (Jump Dash) | experimental PPC only, independent of White Boost Wisp |
| Double Jump | 847000040 | request ID 8 | experimental PPC only |
| Ground Pound | 847000041 | request ID 44 (Stomp) | experimental PPC only |
| Progressive Crouch | 847000042 | copy 1 enables ID 43 (Crawl), copy 2 enables 41 (Slide) | experimental PPC only |
| Swim | 847000043 | underwater jumps | **not gated**: no verified native underwater jump entry |
| Breath | 847000044 | 10-second warning on water entry without item, vanilla duration with item; bubble resets match owned duration | **not gated**: real oxygen/warning timer not identified |

Option: `movement_unlocks: true` (default false). The ordinary Boost Lock
continues to use White Boost Wisp independently; receiving Half/Full Boost
Refill continues to allow native temporary use according to the existing code.

The numerical IDs above are append-only. Existing ID allocations through
847000036 are unchanged. Upgrade requires a NEW seed and .apsonic file. Do not
reuse a journal from another seed.

## Native movement diagnostics

The existing native actor scanner now resolves `player+0x90 -> controller`,
checks PAL player/controller vtables and controller+4 owner, then reports
`controller+0x5c` (current ID), `controller+0x60` (requested/transition ID),
`stats+0x10` and the correlated water flags. Use `/sonicmovement` during play;
`/sonicdebug` provides full evidence. Use `/soniccapsules` when the
Starlight Carnival Act 5 Hover ghost model fails to appear, and `/sonicmap`
while on the Grand World Map to compare AP ownership with native castle cache
handles (not a definitive selectability test). All current-player pointers are resolved
per observation, never retained absolute dump-specific heap addresses.

### Experimental PPC State gate

The verified original PAL word at 0x80033188 is 0x801F0020 (`lwz r0,0x20(r31)`).
The state-machine subobject at `controller+0x40` is strongly supported by
15 independent live dumps. A new opt-in code payload compares the specific
actor's controller with the host-armed one and checks only the requested
state ID. It attempts to bypass the transition to the native post-transition
continuation `0x800331EC` if the required item is absent; no state fields
are changed after entry. **Whether this exit path is valid for all input states
has NOT been verified in the running game.** It may freeze a character, make
transitions repeat, crash Dolphin or prevent scripted progression.

The movement PPC code is *not* included in the four normal Gecko groups; the
existing code handler has insufficient free bytes. It is part of the
`--experimental-direct-hooks` plan when `movement_unlocks` is on. This is a
full replacement of all Gecko hooks, not something to combine with them:

1. Back up Dolphin saves; use a disposable PAL SNCP8P Rev 0 new game.
2. Fully close Dolphin. Disable **all** Gecko codes, including the four AP groups.
3. Start only one Dolphin instance and the AP client with
   `--experimental-direct-hooks SEED.apsonic`.
4. Run `/sonicdebug`, `/sonicmovement` and observe `experimental_direct_hooks`
   and `movement_unlocks` statuses. Install success proves ONLY that RAM bytes
   were written, **not** that Dolphin's JIT executed PPC code.
5. In Tropical Resort Act 1, test Jump Dash, Double Jump, Slide, Crouch with no
   items. If any movement becomes stuck, stop Dolphin and restart without this
   switch. After receiving each AP item, repeat; test death, transitions and
   full game restart. Never combine the experimental hooks with Gecko.

The direct-hook writer verifies exact original/installed instruction bytes and
rejects unexpected code; the branch signature normalizer checks every non-data
PPC word before accepting the patched DOL hash. It cannot certify JIT cache
coherency. Standard Gecko mode is the stable default and keeps vanilla movement.

## Swim/Breath specification (NOT YET IMPLEMENTED)

Swim and Breath are deliberately independent items, as requested:

- Swim absent: prevent native upward/repeated underwater jumps, preserving
  landing, scripted lifts, current-stage interactions and death/respawn.
- Breath absent: native warning countdown should start immediately on water
  entry with **10 seconds** left. Don't grant immediate death; preserve music,
  sound effects, camera effects and vanilla count 5,4,3,2,1.
- Air bubble resets should set 10 seconds without Breath, original native full
  duration **with** Breath (often estimated ~50 seconds, must read actual PAL
  constant rather than guessing).
- Surfacing fully resets the native breath state. Bubble, water-entry and
  surface events should only reset on edges, not every host poll.

The seven `stg510` dump pairs verified `CStateWaterDead` ID 100 and the native
underwater status bits; no oxygen clock or bubble-triggered reset was observed.
`stats+0x34` resets during jumps and is NOT an oxygen counter. The other
suspected effect timer `0x90F992D0` is not a safe patch address. Do NOT write
these fields hoping to force a countdown. `NativeHooks.swim` remains intentionally
blocked. The Swim/Breath items are in the AP pool now, but currently do not
alter underwater gameplay. Aquarium Park stage locations require both items
in conservative logic when the option is enabled; this still needs detailed
route-by-route validation.

## Other current native issues

- Starlight Carnival Act 5: live locked Hover actors 229/308 had no model and
  no published ORC appearance channel. The current capsule helper restores
  native `WaitAppear` using 800D4298; 600F then publishes appearance channel 0.
  Only after that event does a model-less capsule receive its native ghost
  model and locked lifecycle. PPC tests cover waiting, publication, opened
  actors and register preservation. The enemy-wave reproduction with the new
  Gecko profile still needs visual/collision validation in Dolphin.
- Boss unlock on Act 6 first clear: latest source projects authenticated final
  result into pending boss permission before map construction. Needs live test.
- Grand World Map: clearing a boss can temporarily reveal an unowned world
  castle due to cached UI. The Act nodes remain AP-locked, so this is currently
  visual/navigation-only. Must guard native map selection/cache as well as
  persistent permission before calling this resolved.

## Tests and known gaps

Read-only dump probes validate controller identity, current IDs and distinct
water/death states. Pure PPC tests validate encoded branch targets and the
capacity of the optional no-Gecko direct payload. These do **not** execute
Dolphin or provide an Archipelago server. A full AP environment is required
for multiworld seed fill, receipt and Gecko integration tests. Native Swim,
Breath, Hover spawn and cached castle visuals are still unresolved.
