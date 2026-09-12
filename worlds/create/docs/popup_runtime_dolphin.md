# Object popup test: FePuzzleResultsPO (runtime protocol 5)

## Install

1. Close the Create Client and stop CREATE completely.
2. Keep the old CREATE AP Popup Instruction Cache Gecko helper disabled.
3. Install this build's create.apworld and restart the AP Launcher.
4. Boot CREATE fresh without a Dolphin save state, load in-game Save Slot 3,
   and connect the Create Client through the AP Launcher.
5. Check /createpopupstatus: version=5, enabled=1, hooks_applied=1 and a changing
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

## Direct object view and close diagnostics

After the native factory has built AddUnlockImages/Unlock and the UI slot is
registered, AP invokes `_root.stop`, then `_root.DeterminePlaySequence`, on the
same movie reference before returning to the game loop. FePuzzleResultsPO does
not define ShowUnlock; that method belongs to the other Results variant.
DeterminePlaySequence is the PO method that loads the object image/label,
starts the unlock container and increments its stage. The original Unlock
initialization remains intact.

Stopping the PO root at its initial frame prevents the Congratulations timeline
from starting. Its initial mScreen color transform has RGB multipliers 256 and
alpha multiplier 0, while the unlock container is a separate child. The native
PlayOutro still resumes the root at its End label for normal closing.

The normal native close callback remains preferred. After the original game
update, a still-ACTIVE AP popup may invoke OnOutroEnd (0x800336E0) once if its
movie is the same one retained at creation and its root sprite is at frame 374
(zero-based), the PO movie's final frame containing Event_OnOutroEnd and Stop.
Earlier frames, invisible UI alone, a replaced movie or elapsed time never
trigger this fallback. The fallback is marked before calling native cleanup.
It never directly clears a popup pointer or writes the modal layer.

`/createpopupstatus` includes a lifecycle section: popup pointer, native vtable,
callback/context, whether the request was acknowledged, owner active flag,
movie slot/flags, whether that slot has a movie, root frame, modal layer, and
fallback sequence. A closed notification also logs this section. `movie_slot_active`
means the slot contains an asset and movie reference, not proof of visual
visibility or completed animation.

After normal dismissal expect callback_invoked=true, ack_seq=request_seq,
status=0, owner_active=false, popup_pointer=0 and modal=0. If these hold but
input remains unavailable, provide dumps of the broken and playable states;
this build does not guess at other gameplay flags. If callback_invoked=false,
the frame and fallback sequence distinguish an unfinished animation from an
attempted native-close fallback. Live visual/input verification remains required.

## Verified construction and ownership

The vtable bootstrap at 0x805E2C70 still enters the code cave at 0x80006048,
calls the original SimUpdate at 0x8000D880, and lets guest PPC manage its own
instruction writes and cache invalidation. The previous award-mode hook and
FeSimpleMessage availability hook are removed; old revisions require a fresh
boot instead of being overwritten in place.

MakeFePuzzleResults at 0x80031DB0 receives a callback pair and a persistent,
zero-initialized result context at 0x800064D0. Only context+0x10 is 1. A null
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
