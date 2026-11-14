# Native Item Fix 2, 14. November 2026

**Review-Basis:** `Lego-City-Undercover-AP` @ `a871e86d129a7ba4db2468dd6fcc39cd153c9851`.

This patch is limited to local item testing and the reviewed native cheat grant path. It does not establish full seed logic, postgame setup, cheat runtime activation, or in-game validation. Nothing is pushed to GitHub by this patch.

## Why Robber / Astronaut / Miner were silent

`inventory_reader.read_characters()` only emits characters with found, owned or pending bits. A *never found* but valid class therefore has **no row** in `snapshot['characters']`. `TestOverrides._native_state()` previously returned `None` for a missing row, and `apply()` deferred indefinitely without issuing `grant_model()`.

The fix treats the absent row as **not owned**, but only after the native model name has been resolved to a validated ID by `read_model_ids()`. A missing model ID is still an error. Actual success requires a subsequent snapshot showing `owned_byte=1`; a successful request alone is not confirmation. Fresh unowned classes can now be granted via the existing owned-only model write and booth-selection patch. Appearance/selection of every disguise is still subject to live game validation.

## Why every Red Brick cheat returned error 1

In native `item_bridge.cpp`, opcode 3 verified a five-byte prologue at `base+0x7f19a0` before calling the old native cheat unlock routine. The user's live game returned **native signature mismatch** for each attempted cheat, so the routine was not invoked. The source was checked against blob SHA `514e9e8a567b5fc9e4089135494efb4ae7332f3a` from the reviewed commit; its exact replacement span occurs once.

`patch_native_cheat_bridge.py` makes a narrowly scoped alternative: **it does not call `0x7f19a0` at all**, and does not pretend an unknown function signature is safe. It only sets the already-documented serialized **cheat ownership mask bit** at `profile+0xfa80`, after checking:

- Exactly 40 cheat definitions and model index inside the table.
- Correct native cheat definition name hash at the selected index (already verified by the surrounding opcode 3 implementation).
- Current cheat discovery pointer equals `profile+0xfa70`; ownership pointer equals `profile+0xfa80`.
- Loaded/live actor and native opcode eligibility verified by the surrounding dispatch.

The original found/source mask is preserved, as are Red Brick pickup identities, story data and per-cheat activation bytes. It is not the same as forcibly toggling a cheat on in the Extras menu. The client can confirm ownership through a fresh RAM snapshot, then autosave and separately verify the serialized bit for actual AP receipts. The cosmetic/gameplay effect of each cheat requires independent live testing.

## Apply and rebuild

1. Close the game and AP client. Make a **backup of your Steam save**.
2. Extract the package into the root of `Lumas-Archipelago`, overwriting the included files.
3. Run `worlds\lego_city_undercover\tools\RebuildLCUNativeBridge.cmd` (which calls `patch_native_cheat_bridge.py` before building). The patcher is **idempotent** and refuses unknown versions of `item_bridge.cpp` instead of blindly editing them. The original exact source is backed up to `build/lego_city_undercover/item_bridge_before_cheat_fix.cpp`.
4. The builder produces a new `LCUItemBridgeTests_<digest>.dll` and updates the versioned `build/lego_city_undercover/native_items_build.json`. **Restart the GUI** so it picks up that build. If `ziglang` is missing: `.venv\Scripts\python.exe -m pip install ziglang`.
5. Test `Ability: Robber`, `Ability: Miner`, and `Ability: Astronaut` while standing in a normal, non-interaction gameplay state. If `give` is acknowledged in RAM but you cannot select the class, capture the booth screen and log: the remaining issue is a **different native selection/UI gate**.
6. Test a visually easy-to-observe Red Brick cheat, preferably `CHEAT_SCOREX2` or `CHEAT_BRICK_MAGNET`. Wait for **TEST BESTÄTIGT (Spiel-RAM)**, inspect the Extras menu and toggle it normally if required. No screenshot effect is promised by the bit grant alone.

**Expected limitations:** Police removal while that outfit is currently equipped returns native rejection 19 until another outfit is selected. `Invalid bounded diagnostic read` while a save is loading is a separate transient reader state. Warnings about world packages missing `__init__.py` do not cause cheat-grant failures. Local test grants are not AP receipts and their save persistence is not independently proven.

## Test coverage

Seven focused regression tests cover first-time unfound class grants, absence-as-locked semantics, unknown native model rejection, cheat readback, patch idempotence, source-version refusal, and host C++ syntax. The native opcode implementation has **not** been built or executed against the live Windows DX11 game here.

Run tests from repository root:

```powershell
.venv\Scripts\python.exe -m unittest discover -s worlds\lego_city_undercover\tests -p test_native_item_fix_round2.py -v
```
