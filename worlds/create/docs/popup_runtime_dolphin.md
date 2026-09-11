# Experimental Object popup: vtable bootstrap (runtime protocol 3)

## Install and test

1. Close the Create Client and stop CREATE completely in Dolphin.
2. Disable the old **CREATE AP Popup Instruction Cache** Gecko code. This build
   does not require a Gecko helper or an Interpreter CPU setting.
3. Install the accompanying `create.apworld`, then restart the AP Launcher so
   the Create Client loads the new implementation.
4. Boot CREATE fresh, without loading an emulator save state. Load the existing
   in-game Save Slot 3 and connect the Create Client from the AP Launcher.
5. Look for **vtable bootstrap installed (no Gecko)**, then **runtime hook
   heartbeat confirmed**. `/createpopupstatus` should report mailbox version 3,
   `enabled=1`, and `hooks_applied=1`.
6. Test `/createpopup 13` and `/createpopup 6` in the Hub. Confirm that only the
   Object Unlocked view appears, with the matching vanilla image/name, and that
   dismissal restores input.
7. Repeat inside a challenge, including a newly received AP Object. Check that
   gameplay resumes normally and that queued notifications remain in order.
8. Check an ordinary vanilla Create Chain completion as well.

No new seed or APWorld release-version bump is needed. Old code-cave revisions
are rejected; a fresh game boot is required for migration. A client reconnect
can reuse the exact same runtime image without overwriting an active UI owner.
`/createpopupcache` now explains removal of the obsolete helper instead of
printing code. `/createpopupretry` retains the queue and probes for 120 seconds;
it is also available inside challenges when the save-slot state is settled.

## Runtime architecture

Python validates the singleton at `0x806798C0` against the game's vtable
`0x805E2C4C`, the original instructions, the old hook sites, and the reserved
code cave. It writes the immutable runtime image, then redirects only the
**data pointer** at `0x805E2C70` from `0x8000D880` to `0x80006048`.

The wrapper receives the original `SimUpdate(this, const cTime&)` arguments and
calls `0x8000D880` once, before servicing the popup. Guest PPC installs these two
instruction hooks and executes `dcbst`, `sync`, `icbi`, and `isync` itself:

- `0x80091D0C`: type 4 keeps its native object-array builder but uses the existing
  `"unlock"` string at `0x806696F8` for an AP owner. Vanilla uses `"award"` at
  `0x806696F0`. The normal factory Display and destructor paths remain intact.
- `0x800921E0`: the exact AP target ID in r19 returns true without writing an
  unlock threshold. Other IDs return false **within that AP-owned popup**,
  preventing an earlier vanilla candidate from consuming the one-object quota.
  Outside that owner, the original `0x80025560` predicate is called unchanged.

The owner context is checked as well as ACTIVE status. The old heartbeat-call,
scan-start, scan-stop, scan-finish, and direct ShowUnlock hooks are gone. The
primary message is the localized `$GUI_PR_UNLOCK_GAME_OBJECT`, not a blank.
No global unlock function, UI asset, Spark counter, or reward state machine is
modified. Type 4 still builds the image/name array using native game code.

A pending request waits while another modal UI or owner exists, the save guard
is invalid, the native object count at `0x80904C84` does not cover the target, or
`0x80490BF0` returns no record/descriptor. The descriptor must also be eligible
for the native object builder. These checks run on the game thread. Waiting
leaves the mailbox request intact for a later frame.

Popup dispatch no longer depends on Python's MEM2 object-record traversal and
never writes a threshold to display an item. Ordinary Object availability
synchronization retains its existing challenge restrictions. New receipts are
queued independently of that synchronization; existing receipt history is
suppressed when the settled popup session establishes its baseline.

## Removal and diagnostics

Python requests removal through the mailbox and cancels pending dispatch. The
next guest update restores the known original instructions, invalidates their
cache lines, and **only then** restores the vtable pointer. A paused game
completes this sequence on resume. The code cave and active owner are retained
for normal UI dismissal. Unknown third-party instructions are never overwritten;
a guest conflict disables dispatch and is reported as error 5.

A RAM readback alone does not mark the runtime ready. The client requires a
changing heartbeat, the guest's `hooks_applied` acknowledgement, and matching
hook words. If the heartbeat stays zero, provide `/createpopupstatus` after a
fresh boot with the old Gecko helper disabled. Do not enable the old helper to
mask a failed vtable-bootstrap test.

## Verification limits

The local supported DOL and its symbol table confirm the vtable entry,
`cCreateGame::SimUpdate`, both hook instructions, the mode strings, and native
lookup ABI. Inspection of `CreativeChainMsg.gfx` confirms its distinct award
and unlock Display modes and object-array builder. Automated tests execute the
generated patch's integer/control/cache instructions with explicit native-call
test doubles, covering preflight, owner isolation, guest installation/removal,
register/return preservation, and challenge queue behavior.

Two aspects still require a live Dolphin test: whether the virtual call observes
the changed data pointer without cache assistance, and whether type 4's unlock
Display produces the desired visual sequence and restores input in each game
context. These are not claimed as already proven by the automated tests.
No game executable, extracted UI asset, or reverse-engineering dependency is
included in the APWorld package.
