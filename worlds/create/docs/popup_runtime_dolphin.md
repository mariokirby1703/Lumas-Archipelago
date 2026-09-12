# Object popup test: FePuzzleResultsPO (runtime protocol 11)

## Install

1. Close the Create Client and stop CREATE completely.
2. Keep the old CREATE AP Popup Instruction Cache Gecko helper disabled.
3. Install this build's create.apworld and restart the AP Launcher.
4. Boot CREATE fresh without a Dolphin save state, load in-game Save Slot 3,
   and connect the Create Client through the AP Launcher.
5. Check /createpopupstatus: version=11, enabled=1, hooks_applied=1 and a changing
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
requests. At every Dolphin sync the client samples CreateChainsCamera state at
`0x8069A3BC` and the global modal at `0x80948040`. A detected Hub event arms the
gate with the controller's current busy value. Its network popup starts after
the controller has left that captured value and modal is zero for three
consecutive samples. Receipts outside an armed Hub event are not subjected to a
global `chain_state == 0` requirement. The item remains queued; there is no
fixed event timer, and a normal active challenge does not itself block the
queue. Manual test requests remain immediate.

The client logs the world/challenge context, modal value, selected Create Chain
state bytes and elapsed time since the last location check and Object receipt
when an automatic popup is delayed and when it starts. These values are
diagnostic; no gameplay or input flag is written by the popup gate.
For two seconds after an automatic popup closes, modal transitions are also
logged. `/createpopupstatus` reports state stability and the last modal
transition. If the AP popup is inactive while modal is nonzero, it includes the
raw nonzero entries among the first 16 UI-manager slots for diagnosis only.

The intended and live-confirmed result is only the Object Unlocked view with its
native thumbnail. Manual dismissal restores input. Automatic receipt gating
still requires live confirmation around Create Chain and challenge completion
events; the tests do not render the UI.

## Direct object view and close diagnostics

After the native factory has built AddUnlockImages/Unlock and registered the UI
slot, AP sets `mScreen._visible=false`. Protocol 11 then leaves the PO root and
UnlockFrame timelines entirely under ActionScript control. The PO root reaches
its own native DeterminePlaySequence frames after registration; that function
loads the visible `Thumb:` movie and starts `SlideOn`. AP does not invoke
DeterminePlaySequence itself and does not stop, seek or resume either timeline.
There is no fixed display delay.

Each active SimUpdate reads four properties without changing the movie:
`mItemData.length`, the visible image container's `_width`, the native preload
container `mThumbnailContainer0._width`, and the visible image container's
`_visible`. `_framesloaded` is no longer used because its observed payload
decoded to 1.0 even while the rendered thumbnail remained white. `mLoading` and
`mLoadFailed` were removed because the movie only assigns them through its
separate MovieClipLoader listener, while DeterminePlaySequence uses the clip's
direct `loadMovie` method.

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
- movie_item_data_length, visible_thumbnail_width, preloaded_thumbnail_width,
  and visible_thumbnail_container_visible. Each field reports the GFx type,
  decoded value and exact raw payload.
- unlock_count read from the live result object +0x24 (unavailable after deletion).
- object_record_preflight, metadata_ptr, metadata_resolved, and
  thumbnail_identifier_from_metadata, derived from record+0x18 and metadata+0.
- The existing owner, callback, request/ack, modal, movie slot and root frame fields.

The metadata-derived identifier does not itself prove a successful load. The
preload width distinguishes the factory's earlier cache load from the later
visible load. A positive preload width with a zero visible width isolates the
failure to that second load. A GFx type of 0 means that the queried property was
undefined.
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

Protocol 11 also uses the executable's verified zero padding at
0x8062C100..0x8062C450 for the loader diagnostics and their GFx paths. Both
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
