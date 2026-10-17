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
