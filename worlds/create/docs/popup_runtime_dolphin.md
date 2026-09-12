# Object popup test: FePuzzleResultsPO (runtime protocol 12)

## Install

1. Close the Create Client and stop CREATE completely.
2. Keep the old CREATE AP Popup Instruction Cache Gecko helper disabled.
3. Install this build's create.apworld and restart the AP Launcher.
4. Boot CREATE fresh without a Dolphin save state, load in-game Save Slot 3,
   and connect the Create Client through the AP Launcher.
5. Check /createpopupstatus: version=12, enabled=1, hooks_applied=1 and a changing
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

Automatic NetworkItem popups use a separate queue from manual `/createpopup`
requests. Both start at the earliest sync where the popup runtime is idle and
the global modal at `0x80948040` is zero. There is no Chain-state, challenge or
timer gate. A busy modal leaves the item queued for the next sync.

While an AP popup is ACTIVE and CreateChainsCamera state `r3+0x1C` is nonzero,
the hook at `0x8000DB5C` temporarily skips its call to `0x80097EC0`. PENDING and
state zero always run the original update. The hook never writes the controller
state; the original update resumes on the first frame after the AP callback
returns the mailbox to IDLE.

The client logs the world/challenge context, modal value, selected Create Chain
state bytes and elapsed time since the last location check and Object receipt
when an automatic popup is delayed by a modal and when it starts. These values
are diagnostic; no gameplay or input flag is written by the client.
For two seconds after an automatic popup closes, modal transitions are also
logged. `/createpopupstatus` reports state stability and the last modal
transition. If the AP popup is inactive while modal is nonzero, it includes the
raw nonzero entries among the first 16 UI-manager slots for diagnosis only.

The intended and live-confirmed result is only the Object Unlocked view with its
native thumbnail. Manual dismissal restores input. The temporary Chain-update
suspension still requires live confirmation; the tests do not render the UI.

## Direct object view and close diagnostics

After the native factory has built AddUnlockImages/Unlock and registered the UI
slot, AP sets `mScreen._visible=false`. Protocol 12 then leaves the PO root and
UnlockFrame timelines entirely under ActionScript control. The PO root reaches
its own native DeterminePlaySequence frames after registration; that function
loads the visible `Thumb:` movie and starts `SlideOn`. AP does not invoke
DeterminePlaySequence itself and does not stop, seek or resume either timeline.
There is no fixed display delay.

The shared FePuzzleThumbnail UnlockContainer ends by calling
`_root.Event_UnlockFinished`. FePuzzleResultsPO does not define that handler.
Without a handler, a manually-started unlock leaves the root behind after the child animation,
with no PlayOutro and no native cleanup. The previous final-root-frame fallback
cannot resolve this missing event connection and has been removed.

Before scheduling the unlock, this build copies `_level0.PlayOutro` with native
GFx GetVariable (0x8027E73C) / SetVariable (0x8027E864) to
`_root.Event_UnlockFinished` on the AP movie only. The temporary managed value
is released through 0x802E6EFC. The local GFxValue conversion path preserves
function objects via GASValue::SetAsObject (0x801D40B0), which recognizes them
and restores the function value. No vanilla movie is modified.

If handler binding or hiding mScreen fails, AP does not invoke the direct unlock
sequence. The ordinary native Results timeline remains available.

The child completion event should now start PlayOutro, whose final root frame
calls Event_OnOutroEnd. Native OnOutroEnd (0x800336E0) restores modal state and
calls native FeMessageFlow::End; its owner callback acknowledges the AP request.
There is no second polling close path or elapsed-time close trigger.

`/createpopupstatus` includes:

- unlock_finished_handler_bound, popup_phase and show_unlock_called.
- unlock_count read from the live result object +0x24 (unavailable after deletion).
- object_record_preflight, metadata_ptr, metadata_resolved, and
  thumbnail_identifier_from_metadata, derived from record+0x18 and metadata+0.
- The existing owner, callback, request/ack, modal, movie slot and root frame fields.

The metadata-derived identifier and the live-confirmed rendered thumbnail
together establish the working Protocol 12 image path.
There are no independent
native-close, outer-close, availability, AddUnlockImages or Unlock call counters
in this build. These are not inferred or reported as measured calls.

After dismissal expect callback_invoked=true, ack_seq=request_seq, status=0,
owner_active=false, popup_pointer=0 and modal=0.
Test menu, Play, placement and Paint immediately afterwards. Live verification
of the ActionScript event connection and controller input is still required.

## Verified construction and ownership

The vtable bootstrap at 0x805E2C70 still enters the code cave at 0x80006048,
calls the original SimUpdate at 0x8000D880, and lets guest PPC manage its own
instruction writes and cache invalidation. The previous award-mode hook and
FeSimpleMessage availability hook are removed; old revisions require a fresh
boot instead of being overwritten in place.

Protocol 12 also uses the executable's verified zero padding at
0x8062C100..0x8062C450 for the Chain update hook and its guest-side maintenance.
Both
caves must be entirely zero or match this exact runtime image before installation.
No extracted game asset is packaged.

MakeFePuzzleResults at 0x80031DB0 receives a callback pair and a persistent,
result context at 0x800064D0. Context+0x10 is 1. The null-Puzzle path does
not read context+4/+0x0C, which are reused for read-only diagnostics; the
fields it consumes remain zero otherwise. A null
context+0 selects FePuzzleResultsPO.gfx and skips the challenge-specific result
setup at 0x80031F28. Its factory calls FePuzzleResults::UpdateUnlocks with the
sum of context+0x10/+0x14, giving exactly one unlock slot before returning.
The factory also performs native UI/VFX setup; no claim is made that skipping
the challenge-specific block alone proves a particular rendered first frame.

The Object availability hook is at 0x800325E4. The Chain update call hook is at
0x8000DB5C and preserves its original call except during an ACTIVE AP popup with
a nonzero controller state. In the availability builder the result object is
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
