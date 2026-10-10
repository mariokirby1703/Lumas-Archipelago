# October 10 production changes and validation

This release uses slot schema 4. Generate a new seed for its new items/options;
do not attach it to a schema-3 room or delete the old room's journal. The
installed October 10 hotfix (`a292ba58`) remains suitable for that earlier room.
Replace all three AP Gecko codes with the entries from
`data/SNCP8P_capsule_refresh.ini` before testing the new release. Restart Dolphin
after replacement; changing a C2 definition does not replace an already installed
thunk in a running emulation.

## Implemented

* Exact verification of current and known historical capsule C2 payloads,
  including their size and installed return branch. Unknown bytes still reject
  the executable. Historical model-only hooks do not advertise collision refresh.
* Current capsule thunk preserves volatile GPRs, floating-point and paired-single
  registers, FPSCR, GQR0, LR, CR and CTR across native calls; saved state is outside
  the callee argument area. Opened capsules remain excluded.
* Four useful Progressive Game Land Speed items when Game Land is used. Native
  getter, setter and menu hooks cap both selection and simulation at tiers 1–5.
* Final-boss victory requires both Nega-Wisp Armor and Terminal Velocity Act 2.
  Terminal Velocity requires all eight Wisps. A Terminal Velocity starting Act
  exempts only that selected Act; its other Acts and boss remain gated.
* Optional White Boost Lock gates native availability and ordinary Boost-use
  queries without draining the gauge. The separate native Boost provider is
  preserved. Half Boost Refill adds half the actual maximum and clamps at full.
* New Rings filler durably rolls an unbiased integer from 1 through 100 before
  delivery. Historical fixed Rings IDs retain their meanings. Results-screen
  rewards remain deferred; uncertain writes are retained without replaying or
  blocking later receipts.
* Capsule-open reporting uses the native instance transition independently of
  ReceivedItems. In particular, ordinary White capsules with Boost Lock off do
  not wait for a White Wisp item. Native permission enforcement remains separate.
* World-map cache projection covers every native node, including the path to a
  late starting Act. Mandatory Tropical Resort intro Acts remain vanilla. Normal
  late starts open preceding path Acts; the strict single-Act exception applies
  to Terminal Velocity.
* Updated generated YAML, examples, goal presentation and Wisp Capsule Sanity
  placement. Generation prioritizes ordinary World Access before early Wisps so
  low-check seeds cannot strand progression behind Terminal Velocity. Restrictive
  fill retains access items while placing the AP Ring pool and preserves Clear
  locations for the remaining access inventory, including Terminal Velocity starts.

## Actual Dolphin and AP server evidence

These observations used the installed hotfix, not the new schema-4 hooks:

* Read the real capsule hook at `0x800D4824`, target `0x800023D8`, and verified
  its exact historical 62-pair payload and return branch against PAL code.
* User started New Game without `/sonicnewgame`; native mandatory Act 1 and
  fresh state were recognized automatically.
* Collecting Act 1 Red Ring #1 before saving produced `Pickup detected`,
  `LocationChecks sent: [847001001]`, and genuine server
  `Location acknowledged: [847001001]`. The durable journal contains that check.
* User reached the random starting Act, Asteroid Coaster Act 6 (`stg620`), after
  the two required intro Acts. Earlier Asteroid Acts were selectable too.
* The 36-Act native music cue table matched the seed shuffle (35 changed entries).
  User heard changed music. They identified Starlight Carnival while the current
  table entry referenced Planet Wisp; exact active playback attribution therefore
  remains unresolved rather than proven by table readback.
* Cyan Laser permission was enabled while the durable ReceivedItems history
  already contained Cyan Laser Wisp. This is evidence of an owned permission,
  not a successful test of blocking an unowned Wisp.
* Native Boost maxima were 100 in story gameplay and 50 in an original Game Land
  capture. These determine refill amounts; no assumed universal maximum is used.

## Offline evidence and remaining live validation

Tests execute the emitted PowerPC gates across all five speed tiers and profile
changes, preserve capsule calling-convention state with deliberately clobbering
native-call stubs, verify modified original PAL dumps, exercise receipt recovery
and results deferral, and generate reachable seeds. These are offline tests,
not evidence that the new hooks have run in Dolphin.

Live tests still required: new collision/usable capsule refresh; every speed tier
in Game Land; normal and Super Sonic with Boost Lock; visible repeated Rings,
1-Ups, Ring Loss and Half Boost delivery; final boss followed by the escape;
Terminal Velocity's eight-Wisp gate and exact starting-Act exception; and death,
reconnect and restart during those sequences. The user could not perform the
HUD item-delivery test during this session.

Level randomization, Death Link and swimming traps still fail generation with
specific unsupported-capability errors. They are not advertised as playable.
The fresh mandatory intro and durable journal protect attribution, but this
release has not been validated through a complete randomized playthrough.
