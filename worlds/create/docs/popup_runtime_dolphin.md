# Object popup test: Protocol 19 (complete native Hub close)

## Install

1. Close the Create Client and stop CREATE completely.
2. Keep the old CREATE AP Popup Instruction Cache Gecko helper disabled.
3. Install this build's `create.apworld` and restart the AP Launcher.
4. Boot CREATE fresh without a Dolphin save state, load the configured save
   slot, and connect through the Create Client in the AP Launcher.
5. `/createpopupstatus` should report `version=19`, `enabled=1`,
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
publishes `status=PENDING` last. Protocol 19 does not hook the TutorialMessages
queue source at `0x8005C5B0`; the live Protocol-17 log proved that hook lost the
creation race.

The post-creation cleanup checks wrapper `0x8068ED34` and supports both exact
signatures:

- CreateChains completion: callback `0x80099490`, context `0x8069A3A0`
- Hub chain part: callback `0x8005C5B0`, context `0x8068DD50`

For the Hub signature it records the proven saved-modal field at
`wrapper+0x18` and calls the complete native close entry `0x80074D40`. That
entry restores the saved modal through the normal game API before continuing
through `0x80074DA0`, destroying the wrapper and invoking its callback. Because
the callback can immediately create another queued Hub popup, the exact match
and native close repeat up to three times in the same dispatcher frame. No
popup fields or global modal values are modified directly.

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

`/createpopupstatus` reports `hub_wrapper_saved_modal`,
`hub_close_entry_used`, `hub_close_count_this_frame`,
`global_modal_before_hub_close`, `global_modal_after_hub_close`, and
`global_modal_after_ap_close`. For the reproduced race the saved modal and both
Hub-close modal readings should remain `1`, the close entry should be
`0x80074D40`, and the modal after the later natural AP close should be `0`.
