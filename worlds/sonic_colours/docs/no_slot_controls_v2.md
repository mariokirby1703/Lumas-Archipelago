# Sonic Colours PAL: transient no-save Gecko controller index fix V2

## Confirmed user-visible failure

* Game `SNCP8P` Rev0, original PAL hashes and the 11 Gecko C2 hooks are recognized.
* Prologue state is `MANDATORY_PROLOGUE`, `intro_checks_authorized: true`, with a living player and movement C2 armed.
* White capsule configuration fails with `WRITE_BLOCKED: no-slot native index changed`; the native save chain reports `index_out_of_range`.
* White capsules and native boost controls remain unconfigured. This is a client-side bug, not evidence that the music RAM randomizer is broken.

## Change

The prior client assumed exactly `0xFF` for an unsaved intro. Instead the ephemeral Gecko mailbox index is copied from the *observed native container byte* after validating that the snapshot and fresh native reads agree, the save chain rejected the index as out of range, and the scene/player is a corroborated intro of `stg110` or `stg130`. No selected save pointer is synthesized and persistent save writes remain denied.

The C2 revision inspector now accepts inert *stale* transient mailbox indices (4..255) when their nonzero owner pointer exactly matches the current native container. This is needed because Gecko compares the mailbox index to the live native index at runtime: a mismatch cannot grant White/Boost access, but must not invalidate the entire PAL executable. The writer separately demands exact snapshot/native index equality before authorizing changes.

`/sonicstatus` now exposes `native_selected_index_observation` with the read-only trace byte and reason.

## Offline verification

* 42/42 focused regression cases cover bootstrap, transient index 4, 5, 254, 255, stale mailboxes, rogue owner pointer, corrupt control value, all six boost/speed C2 mailboxes and post-save transitions.
* Original PAL `main(4).dol` and all eleven simulated BETA Gecko hooks pass revision verification for these indices.
* No change to Gecko payload bytes, native game save schema, AP item IDs, or music-bank implementation.

**Not yet verified in Dolphin**: White capsule collision/model refresh and true movement block execution. `Swim` and `Breath` are still not natively gated. If White remains available despite `native_gameplay_controls.white_capsules.available == true`, collect a fresh `/sonicstatus`, `/sonicdebug`, and `/soniccapsules` in the same level to investigate the native model/collision lifecycle separately.
