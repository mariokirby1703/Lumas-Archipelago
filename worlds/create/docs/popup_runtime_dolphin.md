# Object popup test: Protocol 18 (nested-modal restore repair)

## Install

1. Close the Create Client and stop CREATE completely.
2. Keep the old CREATE AP Popup Instruction Cache Gecko helper disabled.
3. Install this build's `create.apworld` and restart the AP Launcher.
4. Boot CREATE fresh without a Dolphin save state, load the configured save
   slot, and connect through the Create Client in the AP Launcher.
5. `/createpopupstatus` should report `version=18`, `enabled=1`,
   `hooks_applied=1`, and a changing heartbeat.

A fresh game boot is required because older runtime code may remain in Dolphin's
RAM or instruction cache. No new AP seed is required.

## What this build changes

The Object presentation is the proven Protocol-11 implementation from commit
`ea220093`: CREATE's native `FePuzzleResultsPO` timeline loads the Object image,
shows only the unlock view, calls `PlayOutro`, and performs native cleanup.
Manual `/createpopup` behavior and this timeline are unchanged.

Automatic Object receipts use the same request path. They start when the AP
runtime and global modal layer are idle and the normal RAM/save/native Object
guards pass. There is no Create Chain freeze, event gate, busy/idle sampling,
timer, challenge wait, state-999 wait, or direct thumbnail preload state machine.

The only new guest action targets the later vanilla Chain/Spark notification.
An automatic Object receipt arms suppression only when its
`NetworkItem.location` is one of:

- Hub World Create Chain Part 1
- Hub World Create Chain Part 2
- Hub World Create Chain Part 3
- Hub World Create Chain

The client writes the request's suppression flag before its Object metadata and
publishes `status=PENDING` last. Protocol 18 no longer hooks the TutorialMessages
queue source at `0x8005C5B0`; the live Protocol-17 log proved that hook lost the
creation race.

The post-creation cleanup checks wrapper `0x8068ED34` and supports both exact
signatures:

- CreateChains completion: callback `0x80099490`, context `0x8069A3A0`
- Hub chain part: callback `0x8005C5B0`, context `0x8068DD50`

For the Hub signature it also validates `popup+0x38 == 1`, records the popup's
saved/current modal values, and changes only `popup+0x34` from the nested saved
value to zero. Native `FeMessageFlow::End` at `0x80074DA0` then destroys the
popup, restores modal zero, and invokes its stored callback normally. The code
does not modify `popup+0x38` or write the global modal itself.

The implementation never writes the modal layer or Create Chain state and does
not hook or pause `0x80097EC0`.

## Test

1. Run `/createpopup 13`. Confirm the correct image/name, normal close, and
   working movement, menus, Play, placement, and Paint afterward.
2. Trigger Hub Create Chain Part 1 and receive its real AP Object. Confirm the
   Object popup appears immediately with its image and closes normally.
3. Confirm `Chain complete / Spark awarded` is not visibly shown, the Chain
   continues, and input works.
4. Receive an Object from an unrelated AP location. Its popup should work, but
   it must not arm Chain suppression.

`/createpopupstatus` reports `chain_popup_previous_modal_before`,
`chain_popup_current_modal_before`, `global_modal_after_chain_cleanup`, the
wrapper fields, and `suppressed_chain_popup_count`. For the reproduced race the
three modal diagnostics should be `1`, `1`, and `0`; the wrapper must be inactive
after cleanup and the global modal must remain zero.
