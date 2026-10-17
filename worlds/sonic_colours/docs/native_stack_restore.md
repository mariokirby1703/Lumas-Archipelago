# Native stack restore correction (2026-10-17)

The repeated Game Land crash displayed `Invalid read from 0x00000002,
PC=0x8033be8c`. That PC is inside OSDumpContext, so it describes a secondary
failure while reporting the original exception. Two private captures contain
SRR0/LR `0x01e00000` and r1 `0x8090db08`. All original executable text and
installed native patches in the second capture match their expected bytes.
The user reports bouncing on hanging balls and nearly landing at a checkpoint
for the second occurrence. A historical drown cue is not proof of its cause.

The audit found invalid `lmw r0,offset(r1)` forms in gameplay controls, native
events and the HUD publisher. PowerPC disallows the address-base register in
the destination range of lmw. See the original architecture manual, Book I,
Load Multiple Word (page 71):
https://bitsavers.computerhistory.org/pdf/ibm/powerpc/SR28-5124-01_The_PowerPC_Architecture_May94.pdf

The corrected code loads r2..r31 from their existing save slots, then loads r0
separately. r1 remains the frame base until the existing frame deallocation.
The saved-register layout, mailbox ABI, displaced instruction and all gameplay
permissions are unchanged. No music layout, names or resource changes are made.
The instruction interpreters now reject the invalid form instead of silently
giving it defined semantics. Register-preservation tests execute the actual
scattered event and HUD code and the gameplay gates on both allowed/denied paths.

This is a verified instruction-form correction, **not yet a live-verified cure
for the reported crashes**. Replay the Game Land water exit and hanging-ball /
checkpoint landing with the corrected ISO and client. Test with and without
Dead Weight, movement locks, and active HUD messages; retain any new exception
context if it still fails. Do not set live-validation flags based on unit tests.

Existing seeds and saves can be retained. Repatch the original ISO using the
same player patch and the updated APWorld; the executable component changed.
Do not run the updated native client with the old native ISO: exact-signature
verification deliberately refuses a mixed build. The old generated ISO is kept
intact by the installer. Legacy gameplay-control payloads remain recognized by
their complete original byte sequences for guarded non-native compatibility.

## Verification evidence

- 332 distinct targeted tests passed: gameplay gates, scattered event/HUD
  execution, oxygen, native patching/revision normalization, Rocket guards,
  patch compatibility, packaging, protocol, scoped write proofs and water reads.
- The native-assets matrix generated and filled 1,200 beatable seeds.
- Release ZIP smoke passed imports, beatable fill, player-patch round trip,
  component manifest, native DOL generation and original-asset exclusion.
- The same-seed private test ISO passed WIT DATA verification before and after
  the build; original source hash was rechecked before finalization.
- Native component: `131e58fb3e7f593daa983f66d61251ee417080c88dfe5646f7e7aa04514642b5`.
- Existing crash seed digest remains `80e0a477671b42151c7c5aee0b21ad18`.
- Music names hash remains `6aafc7d6b6f894dad16389001d8ce8cb78db731c6c902fede0ba96f5debdbaef`.
- Boot/gameplay/crash-reproduction live validation remains pending. No live
  validation flags were enabled and no emulated memory was changed during diagnosis.

## Live rejection and actual arena-entry damage

The user reproduced the crash on the corrected stack-restore ISO. Its loaded
component signature was verified as 131e58fb..., so the lmw correction did not
resolve this failure. The first comparison covered the original DOL text and
external patch sites; it did not establish integrity of every arena instruction.

The subsequent comparison of the added arena found the capsule helper's first
instruction at 0x80001800 changed from `9421fe00` (stack allocation) to
`d01f1baf`. The earlier capture contained `d01f03af` at the same address. Thus
its unchanged epilogue deallocates a frame that the damaged entry never creates.
This explains the displaced stack and invalid return captured in OSDumpContext.
The source of this write is not yet identified; do not label it a proven SDK,
Gecko, host-client or game-actor write without observing that writer.

The follow-up native build reserves a 32-byte cache line at the arena start and
moves every code entry and mailbox past it. Branches, PIC-relative addresses,
end-relative mailboxes and the component signature are rebuilt together. Only
the observed first word may vary; modification of the remaining prefix blocks
verification. The original word is exposed in handshake diagnostics.

The handshake now also checks the entry instruction of every arena hook, even
when the component signature and the external DOL branches still match. All
existing complete module inspectors remain in force. The regression test
replays both actual corrupt words into a patched original DOL, verifies that no
entry is damaged, then damages the relocated entry and verifies rejection.
This is containment of the captured corruption; identifying the writer and
confirming crash-free Game Land gameplay remain live tasks.

Follow-up verification: 261 targeted native/patch tests passed, followed by
48 patch/protocol/package/control-proof tests (overlapping subsets). Release
ZIP smoke and original/generated Wii DATA integrity checks passed. The new
component is `fc6c95ea6b774d3a505aa0072c33d573334046443721cacf0cb4ce435884114c`.
The private same-seed ISO is `build/sonic_next_pass/native_arena_guard.iso`.
Live confirmation is pending; relocation would not solve a writer that follows
the relocated hook address instead of writing the fixed low-memory word.

## Client-disconnected control run

The user reports no crash at the same section after restarting the
stack-restore ISO with the AP client closed. This attributes the trigger to
an active host write or client-armed native behavior; it does not distinguish
them or identify the writer. The arena-guard ISO still requires the connected
reproduction test.

An independent host-write firewall now rejects any native-image host write
that overlaps the reserved prefix or any relocated arena hook's first
instruction. It executes before operation-specific guards and backend writes.
The first blocked caller/operation/address/value is logged with a bounded
Python call stack and exposed in diagnostics as latest_blocked_native_write.
Repeated attempts at the same site do not flood the log. This catches a host
writer even if it follows a relocated entry rather than the old fixed address.
It cannot intercept guest-native writes. The connected test is needed to
separate those cases. No ISO change is required beyond native_arena_guard.iso.

52 memory, firewall, scoped-proof, protocol and native-patch tests passed.
