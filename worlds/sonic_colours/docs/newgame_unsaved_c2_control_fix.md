# New-Game no-slot Gecko index fix (PAL SNCP8P Rev0)

## Live failure reproduced from the user log (2026-10-12)

The PAL intro can have a native save-container index of `0xFF` before the first
vanilla save selection. The earlier bootstrap beta correctly recognized this as
`native_unselected_intro_v1` but passed the index to **transient, non-save** C2
control mailboxes. Both `capsule_refresh.inspect_installed()` and
`gameplay_controls.installed()` still rejected every index above 3, producing
`unknown_revision: invalid White capsule control data` immediately after the
first write and disabling all subsequent verified poll operations.

## Change

- `capsule_refresh.valid_native_control_index()` recognizes `0xFF` only when the
  C2 owner is zero (disarmed) or **equals the current, natively resolved save
  container**. Values `4..254` and unrelated nonzero owner pointers remain
  rejected. Values `0..3` retain original handling.
- The same validation is used for every White, Boost and speed C2 control
  mailbox. No Gecko assembly, memory offsets, item IDs or AP schema changed.
- `state.live_control_profile()` also requires exactly native `0xFF` for its
  pre-save fallback, consistent with the verifier. **No selected save bank is
  synthesized or modified.**
- When the game selects index `0..3`, any *stale* C2 index `0xFF` is inert because
  the PPC hook compares it with the native container's current index. Client
  reconfiguration updates the mailbox only with the usual live write guards.

## Verification

- 18/18 isolated no-slot/bootstrap and C2-validation unit tests passed.
- Full original `main(4).dol` PAL binary and all 11 current movement-BETA Gecko
  C2 payloads were simulated, including their real return branches. The native
  revision check passed before injection, after all hook installations, after
  writing `0xFF` to White / Boost / speed control data, and after transitioning
  the native selected byte from `0xFF` to `1`.
- This is an **offline** verification, not a Dolphin live guarantee. Swim/Breath
  native locks still do not exist in this beta.

## Installation / next diagnostic

Replace only `custom_worlds/sonic_colours.apworld`, restart Archipelago and
Dolphin. Keep the existing **Movement Gecko BETA** ini unchanged, with its four
replacement groups enabled, and do NOT enable `--experimental-direct-hooks`.
Use the matching current Schema-7 `.apsonic` and seed. Start Sonic's new game
with client connected. In Tropical Resort Act 1 request `/sonicstatus` and
`/sonicmovement`; verify `intro_checks_authorized`, `current_disc_verified`,
`operation_status.capsule_refresh`, `operation_status.native_gameplay_controls`
and `movement_unlocks`. Collect a Red Ring and confirm a network LocationChecks
acknowledgement. Do not reuse a prior experimental RAM-hook savestate.
