# Separate detective scan entitlement

The separate lock is now implemented; the earlier status describing a
story-only detective scan is superseded by this document.

## Native gate

AllowDetectiveMode's action handler is RVA 0x105620. It resolves the character
and calls 0x649a0(actor, allowed). The setter selects a 0x5330-byte player record
at RVA 0x17ece50 and updates +0x51, then emits a native permission event. This
is independent of the global 51-entry Scanner ability (criminal/person scan).

The bridge installs a pinned, exact-15-byte-signature checked detour at 0x649a0.
Copied instructions are whole and have no RIP-relative operands. The trampoline
keeps original setter semantics. Managed but unreceived Detective Scan clamps
`requested=true` to false, so repeated script grants cannot override the lock.
Granting the item permits the original request; it does not force aura activation
or grant Police. Removal clears the current actor's existing native permission.
Policy mutation requires ordinary live-player context 46 and never interrupts an
already running scan. The wrapper affects subsequent setter requests for both players;
initial permission clearing targets the current controlled actor.

The DLL and trampoline remain valid for the game process lifetime. If an older
version of this detour is already installed, the signature check refuses to overwrite
it; restarting the game clears that old process-local patch.

## AP and local tests

New item: `Ability: Detective Scan`, ID 2213734077, progression.
`detective_scan_lock` defaults on for newly generated seeds. It requires ability
items to be managed. Legacy seeds with no such option are deliberately unchanged:
they have no location containing this newly introduced item. The test UI can still
give/remove it, allowing the lock to be tested on an existing seed.

Effect plan: runtime_unlock / DetectiveScan. It is not appended to the real
51-entry ability table. Native policy uses the existing reserved policy word:
bit 0 managed, bit 1 entitled; entitlement without management is rejected.
Opcode 20 provides verified local test grants/removals. Normal AP policy is
reconciled from received items on reconnect/reload. Police alone has no Detective
Scan entitlement. The requested broader progressive-class scheme remains separate
work; this patch introduces the actual standalone scan lock.

The entitlement is durable in the AP receipt journal. Runtime verification is
recorded as `runtime_verified`, not a fabricated native save bit or disk proof.
The UI explicitly distinguishes this persistence from model/ability save flags.
Local test overrides remain client-session rules and do not alter AP receipts.

After granting while inside an aura, step out and back in: a previously rejected
script activation is not replayed by the grant. This preserves normal proximity
requirements. An active scan must finish before changing this permission.

## Generation and validation

The updated chronological test YAML enables `early_detective_scan` as well as
`early_criminal_scan`. Both separate scans and Police are placed on observed opening
checks by pre-fill / local early-fill, and the template is exercised through a
complete fill and reachability checks. General story logic remains partial.
An existing seed cannot gain a new randomized item simply by installing the client.

Tests execute the actual native detour against an isolated fake setter in synthetic
memory: deny, grant, original false request, vanilla policy, unknown signature.
Python tests cover independent Police/Detective policy, legacy seed compatibility,
durable runtime receipts, GUI overrides and early Detective placement. These tests
do not constitute live visual confirmation. The last live read saw RideAlong
(context 11), so no gate mutation was performed in the running game yet.
