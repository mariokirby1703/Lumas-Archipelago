# Object popup test: Protocol 14 (Protocol 11 timeline + Chain suppression)

## Install

1. Close the Create Client and stop CREATE completely.
2. Keep the old CREATE AP Popup Instruction Cache Gecko helper disabled.
3. Install this build's `create.apworld` and restart the AP Launcher.
4. Boot CREATE fresh without a Dolphin save state, load the configured save
   slot, and connect through the Create Client in the AP Launcher.
5. `/createpopupstatus` should report `version=14`, `enabled=1`,
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

The flag is armed only after the AP Object popup becomes active. Once that AP
popup has closed, the post-update dispatcher checks wrapper `0x8068ED34`. It
calls native `FeMessageFlow::End` at `0x80074DA0` exactly once only if the
wrapper has a popup, is active, and contains callback `0x80099490` with context
`0x8069A3A0`. Native End destroys the visual popup and invokes its stored Chain
callback, allowing CreateChainsCamera to continue normally.

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

`/createpopupstatus` reports `suppress_next_chain_popup`, the Chain wrapper's
popup pointer/active/callback/context fields, and
`suppressed_chain_popup_count`. After a successful Hub test the flag should be
zero and the count should have increased by one.
