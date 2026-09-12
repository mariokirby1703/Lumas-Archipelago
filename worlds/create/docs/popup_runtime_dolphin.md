# Object popup isolation test: Protocol 6 baseline

This build restores the popup guest runtime from commit `02833474` unchanged.
It intentionally excludes the later thumbnail, Create Chain freeze, Hub gate,
busy/idle sampling, timer, challenge-wait, and child-preload experiments. The
current client-side NetworkItem receive queue remains enabled.

## Install

1. Close the Create Client and stop CREATE completely.
2. Keep the old CREATE AP Popup Instruction Cache Gecko helper disabled.
3. Install this build's `create.apworld` and restart the AP Launcher.
4. Boot CREATE fresh without a Dolphin save state, load the configured in-game
   save slot, and connect the Create Client through the AP Launcher.
5. Run `/createpopupstatus`. Expect `version=6`, `enabled=1`,
   `hooks_applied=1`, and a changing heartbeat.

A fresh CREATE boot is required because a newer popup protocol may still be in
Dolphin's RAM and instruction cache. No new AP seed is required.

## Required baseline tests

First run `/createpopup 13` in the Hub/world:

- An Object popup should appear. A white/missing thumbnail is expected in this
  baseline and is outside this test.
- Close the popup normally.
- Immediately test movement, menus, Play, placement, and Paint.

Then receive a real AP Object from Hub Create Chain Part 1:

- The ordinary AP receive message should appear in the client.
- The Object should be queued automatically and its popup should start as soon
  as the global modal layer is free.
- The running Create Chain must not be paused or modified.
- Close the popup and test input again.

Automatic NetworkItem popups and manual commands use separate FIFO queues.
Initial receipt history is not replayed. New Object receipts are collected once,
including duplicates, and remain queued while another modal or AP popup is open.
There is no Chain-state, challenge-state, elapsed-time, or post-location gate.

If either test produces no popup or leaves input locked, run
`/createpopupstatus` immediately and capture the full client output. Useful
fields include `status`, `popup_pointer`, `modal`, `owner_active`,
`request_seq`, `ack_seq`, `callback_invoked`, and `heartbeat`.

## Restored runtime behavior

Protocol 6 constructs `FePuzzleResultsPO` with one synthetic Object reward,
registers its native UI slot, binds `_root.Event_UnlockFinished` to
`PlayOutro`, and calls `_root.stop` followed by
`_root.DeterminePlaySequence`. Native `Event_OnOutroEnd` owns modal teardown,
result destruction, and the acknowledgement callback.

The runtime hooks only the simulation vtable bootstrap and the scoped Object
availability predicate at `0x800325E4`. The original Create Chain call at
`0x8000DB5C` is required and is never replaced. No popup code is installed in
the later auxiliary cave at `0x8062C100`.

The next thumbnail experiment waits until both manual and real NetworkItem
baseline paths are confirmed in Dolphin.
