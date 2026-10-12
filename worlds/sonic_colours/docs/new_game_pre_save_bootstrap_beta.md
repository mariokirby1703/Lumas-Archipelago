# New Game before save selection: AP bootstrap fix (experimental)

Applies to **Sonic Colours (Wii), PAL SNCP8P revision 0, Schema 7**. This is a correction to the Movement Gecko BETA client, **not** a new Gecko/PPC payload. Keep the SAME Movement Gecko BETA INI (do not mix with the four normal groups). Original RAM music shuffling remains unchanged.

## Bug reproduced from October 12 user logs

- First native act: `stg110` on a new game before vanilla save selection.
- `save_container_unavailable: index_out_of_range`, `UNBOUND_BOOTSTRAP`, `save_armed=false`.
- Music bank rewrites at `0x9017E8A0` continue; checks do not send, White/Boost C2 data and movement C2 mask are not armed.
- The client used to return immediately when the save index was invalid, with `stable_polls=0`, so the new game guard could **never** start.
- The network check transmitter also mixed in durable journal checks unconditionally, bypassing the intended current-scene save-guard boundary. Now it transmits only what `Runtime.poll` has authorized.

## New path

1. While there is no selected save (native out-of-range index), require the **actual** `stg110` stage, original clicked slot `0:1`, living native player with zero initial Rings, first-stage Red Ring bitmap zero and native death counter zero. Read those through the verified actor chain; require 3 coherent polls. An invalid save index alone NEVER authorizes the bootstrap.
2. Keep scene-local stable polls across repeated no-save reads. Create an AP-seed-specific, journaled **ephemeral** intro epoch, not a made-up native save identity.
3. On `stg110` / `stg130`, journal + send only **directly observed** native Red Ring, capsule, and final-result checks immediately before save select. No previous save-bit import; no arbitrary location credit. Received AP inventory remains tied to authenticated server/team/slot/seed.
4. Live actor stats, White/Random capsule and regular Boost Gecko controls may use the native container and its **actual** index byte even while out of range. This ONLY applies to the recognized original C2 control words. Never compute a selected-save address for the nonexistent slot or write native progress flags. The movement control also accepts the verified living intro player without `progress_verified`.
5. On the later vanilla save selection, match two previously witnessed result events to the native saved records by exact score + rank, and require both intro clears. Only THEN bind the journal's seed epoch to that save/profile/index. If the records don't match, stay unbound. The working-record/read path remains separate.
6. On any session or stage identity mismatch, stop authorization. An old/new journal cannot automatically inherit an unbound previous session's events. No unsafe replay of uncertain consumable writes.

## Scope and limitations

**Offline tests only.** The new no-save profile binding requires Dolphin live verification. In particular, the native pointer used by the C2 hook must still be confirmed to match its real container/index comparison, and the two saved score records must match the recorded final result UI. A false or mismatched score correctly blocks binding until additional native research.

`Swim` and `Breath` are separate AP items but their actual native water/oxygen locks have **not** yet been implemented. No supposed oxygen timer or blind RAM write is included. Similarly, Grand Map repair and the scripted Starlight Carnival 5 Hover spawn are not claimed fixed here.

A client started *after* the first-act initial evidence has been missed cannot safely infer a new playthrough from zero progress. Start the AP client and connect to the new seed **before choosing New Game**. Tests that already advanced past the virgin intro should restart with a new matching seed/new save (never reuse a finished save with a different server seed).

## Suggested manual test

1. Back up existing APWorld, YAML, seed and emulator save. Install this new APWorld only (same Movement Gecko BETA profile remains enabled), then restart Archipelago and Dolphin.
2. Connect to a **fresh** matching Schema 7 AP seed at the title screen, then choose New Game. No save slot selection yet.
3. In untouched `stg110` idle use `/sonicstatus`: expect `intro_proof: native_unselected_intro_v1`, `intro_checks_authorized: true`, `save_armed: false`, `playthrough_state: MANDATORY_PROLOGUE`. `save_armed:false` is EXPECTED until actual slot selection.
4. Obtain a Red Ring; verify `LocationChecks sent` and `Location acknowledged` BEFORE entering save selection. Verify White capsule ghost, regular Boost Lock and `/sonicmovement` native gate status while alive. Any `WRITE_BLOCKED` reason must be captured exactly.
5. Finish both mandatory intro Acts; check final result grades/checks reach the AP server immediately. Select a vanilla save slot and check `/sonicbinding` and `/sonicstatus`: eventual `save_armed:true`, and no repeated/redelivered checks.
6. Switch saves, restart/reconnect, and verify the journal refuses unauthorized new progression on other native slots.

## Source changes

- `client/hooks.py`: no-selected-slot intro witness and scene-local poll stability.
- `client/state.py`: ephemeral gate and strict actor-only C2 control profile, no fake selected-save pointer.
- `client/binding.py`: seed-local native result witness reconciliation on save selection.
- `client/runtime.py`: native result receipt scores, no old-save progression import during bootstrap, gated check return.
- `client/capsule_refresh.py` and `client/gameplay_controls.py`: guarded original no-selected-slot container/index C2 data.
- `client/client.py`: transport does not reimport journal checks when current scene not authorized.
- `client/diagnostics.py`: explicit `intro_proof`, `intro_checks_authorized` and `persistent_save_bound`.
- `test/test_new_game_no_slot.py`: regression and wrong-profile/security tests.

Run `python tools/run_bootstrap_isolated.py` for the targeted mocked PAL native scene tests when full Archipelago core isn't installed. Those tests are **not** substitutes for Dolphin gameplay.
