# Object popup test: Protocol 17 (atomic source suppression)

## Install

1. Close the Create Client and stop CREATE completely.
2. Keep the old CREATE AP Popup Instruction Cache Gecko helper disabled.
3. Install this build's `create.apworld` and restart the AP Launcher.
4. Boot CREATE fresh without a Dolphin save state, load the configured save
   slot, and connect through the Create Client in the AP Launcher.
5. `/createpopupstatus` should report `version=17`, `enabled=1`,
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
publishes `status=PENDING` last. The hook at `0x8005C5B0` intercepts the matching
`0x8068DD50` three-entry TutorialMessages queue only while that same AP request
is `ACTIVE`, before its call to `0x80074B20`. It records the queue, clears entries
`+0x04/+0x08/+0x0C`, leaves state bytes `+0x00/+0x01` as `1/0`, clears the AP
flag, adds the number of nonzero entries to the suppression counter, and returns
without creating a popup or entering modal flow.

When the flag, ACTIVE status, or context does not match, the hook executes the displaced
`stwu r1,-0x30(r1)` and resumes vanilla at `0x8005C5B4`. An invocation with an
empty queue leaves suppression armed for a later call carrying entries.

The older post-creation fallback checks wrapper `0x8068ED34` and calls native
`FeMessageFlow::End` at `0x80074DA0` only for this separate signature:

- CreateChains completion: callback `0x80099490`, context `0x8069A3A0`

Native End destroys that fallback popup and invokes its stored callback. The
`0x8005C5B0/0x8068DD50` path is never intentionally allowed to create one.

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

`/createpopupstatus` reports the Hub queue entries and state bytes before/after,
`hub_queue_source_suppressed_count`, the fallback wrapper fields, and its
`suppressed_chain_popup_count`. After a successful Hub test the AP flag should
be zero, all three after-entries should be zero, after-flags should be `1/0`,
and the source-suppressed count should increase by the number of consumed
nonzero entries.
