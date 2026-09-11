# Object popup test: FePuzzleResultsPO (runtime protocol 4)

## Install

1. Close the Create Client and stop CREATE completely.
2. Keep the old CREATE AP Popup Instruction Cache Gecko helper disabled.
3. Install this build's create.apworld and restart the AP Launcher.
4. Boot CREATE fresh without a Dolphin save state, load in-game Save Slot 3,
   and connect the Create Client through the AP Launcher.
5. Check /createpopupstatus: version=4, enabled=1, hooks_applied=1 and a changing
   heartbeat. No new AP seed or APWorld release version is required.

## Test both manual and real AP receipts

- /createpopup 13 should display Automatic Rocket; /createpopup 6 Jumbo Ramp.
- Receive an actual AP Object item: the normal AP receive log remains enabled
  and the Object is automatically queued for this same popup implementation.
- Receive several items while a popup or another modal is open. Dismiss each;
  check receipt order, matching images/names, and normal controller input.
- Repeat within a challenge. Python must not resolve/write Object records just
  to show the notification. Native registry readiness and modal checks defer it.
- Initial receipt history is not replayed. New ReceivedItems packets are handled
  directly and the polling cursor prevents duplicate enqueueing.
- Verify an ordinary vanilla challenge completion and Create Chain as well.

The intended result is only the Object Unlocked view. Its visual startup,
dismissal/input restoration and real Dolphin vtable bootstrap still require
live confirmation; the tests do not render the UI. If an empty results/Spark
state appears first, capture that behavior and /createpopupstatus. This build
uses the confirmed Results movie rather than the Chain or PuzzleUnlock movie.

## Verified construction and ownership

The vtable bootstrap at 0x805E2C70 still enters the code cave at 0x80006048,
calls the original SimUpdate at 0x8000D880, and lets guest PPC manage its own
instruction writes and cache invalidation. The previous award-mode hook and
FeSimpleMessage availability hook are removed; old revisions require a fresh
boot instead of being overwritten in place.

MakeFePuzzleResults at 0x80031DB0 receives a callback pair and a persistent,
zero-initialized result context at 0x80006450. Only context+0x10 is 1. A null
context+0 selects FePuzzleResultsPO.gfx and skips the challenge-specific result
setup at 0x80031F28. Its factory calls FePuzzleResults::UpdateUnlocks with the
sum of context+0x10/+0x14, giving exactly one unlock slot before returning.
The factory also performs native UI/VFX setup; no claim is made that skipping
the challenge-specific block alone proves a particular rendered first frame.

Only the code hook at 0x800325E4 remains. In this builder the result object is
r29 and the scanned global Object ID is r17. ACTIVE status and the AP owner
callback context must match. The exact target returns true; other Objects in
that AP scan return false. A vanilla result object calls the original Spark
threshold predicate at 0x80025560 unchanged. Native preflight first requires
an available registry, target record, descriptor and unlockable descriptor flag.
No temporary threshold writes or Spark awards are used for AP display.

After the factory returns, the AP owner stores the result pointer. The movie
slot at result+0x14 must exist and be loaded before UI registration with
0x804EA4D0(manager=0x80947A30, index=(slot-0x80947F50)/24, 0, 1), matching the
normal caller at 0x800456F4..0x80045758.

The result callback invokes native FeMessageFlow::End through 0x80074D90 with
our separate owner. This releases the object/UI slot, clears the pointer,
invokes the mailbox acknowledgement, then clears owner.active. The result
class restores modal state through its own OnOutroEnd at 0x800336E0; AP does
not write the modal layer. Callback data and owner memory survive uninstall.

Python requests removal via enabled=0. Guest code restores the original
instruction, invalidates its cache line, then restores the vtable pointer.
A paused game completes removal on resume. Foreign instructions are preserved
and disable dispatch with error 5. Readback alone is insufficient for readiness:
heartbeat, guest acknowledgement and hook words must agree.

## Scope and evidence

The supported local DOL/symbols and extracted UI actions confirm the factory,
null-context branch, builder, hook ABI, registration and close paths. The new
external dump interpretation is consistent with those local files; the remote
/mnt/data RAW dumps themselves are not present in this workspace.

Tests decode the emitted PPC integer/control/cache instructions with native
call doubles, covering factory arguments, UI-slot registration, register/return
preservation, owner isolation, target selection, preflight, guest removal,
request ordering and real ReceivedItems event integration. No game binaries,
extracted UI assets, or reverse-engineering dependencies are packaged.
