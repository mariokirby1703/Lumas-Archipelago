# Marble Saga Kororinpa / Marbles! Balance Challenge — Unified AP/RAM Notes

Date: 2026-07-11
Last updated: 2026-08-06
Version/context: PAL / Marbles! Balance Challenge / RK6P18.
Primary target: external Dolphin Archipelago client, no ISO modding at first.
Current mapping focus: Easy / Normal / Hard difficulty RAM mapping, Wii Balance Board stage detection, Stage-ID mode/source separation, Crystal Sanity prep, Save Slot 3 unless stated otherwise.

This is a consolidated single notes file built from the previous split notes plus the latest chat discoveries, updated through the 2026-07-11 AP client/RAM-mapping session: combined in-level detection, exact entered-stage identity, Easy/Hard address predictions, Hard Ant structure, indirect junk reward detection, AP-side progression counters, marble popup suppression, Mirror/Normal result sync, Save Slot selection safety, Wii Balance Board level identification/check detection, transient goal-reached candidates, Blackout Trap candidate, third-party PAL/NTSC address-table reconciliation, PAL World Map/Free Mode Stage IDs, mode/source flags, current marble address, current crystal count candidate, and Crystal Sanity planning.

2026-08-03 update highlights:
- Recipe AP items use a confirmed subset of direct unlock bytes in `804DF4E0`-`804DF4FC`, not a complete continuous range.
- AP-sent junk items should write both live/current counts (`804DF4A2+`) and saved/persistent counts (`9046F74E+`) so Junk Factory inventory sees them.
- Vehicle cutscene/manual bonus-level gates are confirmed: Easy `804DF903`, Normal `804DF908`; use `31` for the W5/Submarine-side cutscene, `79` for the W6/Rocket-side cutscene, and `95` only when both are AP-authorized for that difficulty.
- These vehicle gate bytes allow manual AP unlocks for Candy Island L1, Haunted House L1, City L1, Haunted House L5, and City L5 without globally pretending both vanilla cutscenes have been watched.

2026-08-06 implementation / test-client update highlights:
- `client_test/full_ap_ram_test_client.py` is the current complete RAM test harness. It generates AP-style locations/items, randomizes rewards by seed, watches checks, and can write RAM with `--apply`.
- Current test command:

```powershell
python client_test/full_ap_ram_test_client.py --apply --assume-slot-3 --experimental-traps
```

- Current pytest command:

```powershell
python -m pytest client_test
```

- Current tests pass with 27 client-test tests.
- Save Slot 3 safety is active. Selecting save slot value `2` arms writes; `--assume-slot-3` bypasses that for local testing.
- The generated test profile currently uses Bronze trophy locations only, includes Tutorials 1-10, and excludes Wii Balance Board locations to avoid flooding early spheres.
- Starting inventory gives one random starting marble from the 20-marble list. New AP-granted marbles are written as `1` in menus; already-used marbles may remain `2` and must not be forced back to `1`.
- AP-owned Figure Roller heads follow the same new/unseen rule as marbles. If the Figure Roller marble is owned, Charlie is considered usable.
- AP-sent normal junk filler writes one item at a time to both live/current `804DF4A2+` and saved/persistent `9046F74E+`.
- World Access items are difficulty-specific. W5 also requires `Submarine`; W6 also requires `Rocket Ship`; Hard worlds require `Hard Mode`.
- Hard Mode is written to `804DF5F4`.
- Submarine is written to `804DF57F`; Rocket Ship is written to `804DF580`.
- Vehicle cutscene/manual bonus-level gates are written per difficulty only when the corresponding AP progression is owned: `15` none, `31` W5/Submarine side, `79` W6/Rocket side, `95` both.
- Bonus levels are AP-owned individually. New AP bonus levels are written as `1` outside levels. While in a level, unowned bonus levels are held at `2` as a popup guard. In the goal of a bonus level, bonus states are lowered from `2` back to owned `1` or unowned `0` to block vanilla "Next Level" from entering the next AP-locked bonus level.
- Pickup detection now baselines Green/Stump/Junk temp bytes on every stage identity change. This prevents stale values from the previous goal/result from falsely sending the next level's Green Gem when the player mashes into the next level.
- Goal detection currently has three paths:
  - transient goal-reached candidate group `90144168` through `90459ED7`;
  - Stage Cleared fallback `8048D1B5` values `94` / `95`;
  - L11 Trophy fallback: if an L11 Trophy location is observed, the matching `W?L11 ... Goal` location is also sent.
- L11 levels do not reliably hit the transient goal-reached candidate group because the game can award the trophy and immediately leave the level instead of showing the normal goal/result screen.
- All W1-W6 L11 state bytes across Easy/Normal/Hard are approved write targets for event guarding. On the world map, dangerous `State=3` values are forced down to `0` so vanilla world/vehicle cutscenes and next-world side effects do not fire from AP's temporary state writes.
- `Junk Factory Access` is separate from W1L11 completion. It temporarily sets W1L11 state to `3` only in safe Anthony's House / Junk Factory contexts, including the early Anthony entry mode `8049D96F == 35`. It restores previous W1L11 states outside that context and hides unsafe `3` values.
- Current hub/screen values used by the client:
  - `804E612F == 6`: Anthony's House
  - `804E612F == 8`: world/level select
  - `804E612F == 12`: Junk Factory
  - `804E612F == 255`: none/world map style context
- Experimental traps:
  - `Blackout Trap`: `80490A42 = 3` for 10 seconds, only during safe active gameplay. It is forced to `0` at goal/outside safe gameplay, and its timer does not tick in menus/result/goal.
  - `Mirror Trap`: uses active/result slot `8049D96B`, writes before level load, and clears at goal.
  - `Inverse Controls Trap`: uses `8049D96B`, activates only during safe active gameplay, lasts until goal or 60 active-play seconds.
  - `Noclip Trap`: uses `80CBD6EB = 0` for 3 active-play seconds and restores collision with `80CBD6EB = 1` outside safe gameplay or at goal.
- Safe active gameplay currently requires in-level, `804881AF == 1`, no transient goal active, and `8048D1B5` not in `{94, 95}`.
- `Reset Trap` candidate `807AC8C1 = 32` remains rejected/unsafe for now because reset/cutscene/wipe behavior is not consistent across levels.
- `Victory` is currently fixed to `W7L10 Normal Goal` in the RAM test profile.

---

## 1. Baseline / AP Client Goal

Goal:
- Detect checks automatically and send them to Archipelago.
- Receive AP items and apply safe unlock effects through Dolphin RAM where possible.
- Avoid writing collectible/check flags in a way that would create false AP checks.
- Keep AP world progression authoritative where possible.

Current design direction:
- Use Save Slot 3 as the AP slot.
- Existing players may already have normal saves in Slot 1 or Slot 2.
- The mapped progress blocks appear to be fixed save-slot data loaded before save-file selection, not simply “currently selected save” data.
- `8049D99F` stores the selected save-file index in the save-file selection UI: `0=Slot 1`, `1=Slot 2`, `2=Slot 3`. This is useful as a safety/menu heuristic, but should not be treated as the only proof of which save block is active in memory.

Recommended AP warning:

```text
This Archipelago client reads and writes Save Slot 3.
Please back up your save data before playing.
```

---

## 2. Address / Tooling Notes

### DME / MEM2 address display quirk

When scanning saved MEM2 addresses around `0x9046F766`, Dolphin Memory Engine may display results as `0x01C6F766`-style addresses.

Observed mapping:

```text
Wii/PPC address = DME displayed address + 0x8E800000
DME displayed address = Wii/PPC address - 0x8E800000
```

Example:

```text
0x01C6F767 + 0x8E800000 = 0x9046F767
```

Notes:
- Keep documenting the real Wii/PPC addresses, e.g. `0x9046F767`, not the `0x01C6...` display form.
- DME search end ranges may behave effectively exclusive, so scanning through `0x9046F76F` may require entering an end like `0x9046F770`.

---

## 3. Core Read/Write Safety Rules

### Do not write AP received items to check/collectible flags

Do **not** write AP received items to:
- Green Gem flags
- Stump Temple Piece flags
- Trophy flags
- Other collectible/check flags in general

Reasons:
- Writing them would falsely trigger AP locations/checks.
- It can also remove one-time collectibles from levels, e.g. Green Gems disappear after being marked collected.
- Green/Stump totals can update immediately when these flags change.

### Level State writes are safer, but still need rules

Level State addresses are confirmed writable and can unlock levels.

Observed:
- Changing a Level State from `0` to `1` manually unlocks that level in-game.
- This can let the player enter worlds that would normally require special vanilla requirements, until vanilla events reassert those requirements.

Recommended write behavior:

```python
def unlock_level_state(addr):
    value = read_u8(addr)
    if value == 0:
        write_u8(addr, 1)
```

Never lower normal level state values during routine unlocks:

```python
new_value = max(current_value, received_value)
```

Exception:
- Dangerous L11 event-guard handling may intentionally lower unsafe L11 `State=3` values outside levels.
- Current RAM test behavior is stricter on the world map: W1-W6 L11 states across Easy/Normal/Hard are forced to `0` when they are `3` and not needed for a safe Anthony's House / Junk Factory context.
- Do not perform this cleanup while inside a level.

### Level State values

Current interpretation:

| Value | Meaning |
|---:|---|
| `0` | locked / not unlocked |
| `1` | unlocked / new / enterable |
| `2` | unlocked/seen/played but not completed |
| `3` | completed; trophy icon can be shown |
| `4+` | not useful currently; trophy icon hidden like non-completed states |

Observation:
- Changing completed Level 11 state from `3` back to `2` or `4+` hides the trophy icon in level select.
- The Trophy byte itself does not change, but the UI trophy display is gated by State `3`.

---

## 4. World Progression / L11 State-Machine Problem

Important behavior:
- Level State addresses are writable, but Level 11 State values are not merely cosmetic.
- A Level 11 State of `3` is used by vanilla as a visibility/progression/gate signal in several places.
- A real Level 11 completion event can perform additional one-time vanilla actions, such as unlocking the first five levels of the next world.
- Manual writes and real completions are therefore different:
  - Manually setting an L11 State to `3` does **not** automatically set the next world's L1-L5 states to `1`.
  - A real L11 completion **does** trigger the next-world L1-L5 unlock batch.
  - Even if the L11 State was manually set to `3` beforehand, completing the L11 again can still trigger the real-completion unlock batch.

Practical AP rule:
- AP World Access items must remain authoritative.
- Do not treat `L11 State == 3` by itself as proof of an AP location/check.
- Do not allow vanilla L11 completion to permanently grant the next world's L1-L5 if the corresponding AP World Access item has not been received.
- If vanilla sets next-world L1-L5 to `1` after a real L11 completion, the client should undo those `1` values unless AP allows that world. Do not lower `2` or `3` during this cleanup.

### Deprecated yellow crystal / context hypothesis

The value previously called the **yellow crystal/context flag** is **not reliable as a screen/context flag**.

Observed problems:
- It only switched to apparently useful values like `8` or `36` after the player had previously visited Anthony's House / value `20` after a level completion.
- It can be affected by the number of yellow crystals in a level; levels with more than 8 yellow crystals can change the value simply because that many crystals exist/are collected.
- Therefore it is likely a yellow-crystal-related value, reward/cache value, or UI side value, not a clean screen-state.

AP rule:
- Do **not** use the old yellow value for L11 gating.
- Do **not** use the old yellow value for vehicle gating.
- Do **not** use the old yellow value to decide whether Level Select / World Map / Anthony's House is active.

### Reliable current-stage identity values

These addresses are currently the best way to identify the exact stage/level the player entered. They should be snapshotted only when the combined in-level detector transitions from outside-level to in-level.

Important naming update:
- `8049D94D` is better called **selected/entered stage index**, not only “level index”.
- In normal world level select it means `0=L1`, `1=L2`, ..., `10=L11`.
- In Wii Balance Board mode it means Balance Board stage index `0-99`.

| Address | Meaning | Values / Notes |
|---:|---|---|
| `8049D945` | current/last entered world or mode index | Normal/bonus worlds: `0=W1`, `1=W2`, `2=W3`, `3=W4`, `4=W5`, `5=W6`, `6=W7`, `7=WA`, `8=WB` likely, `9=WC`; `14=Wii Balance Board level select / Wii Balance Board level`. Updates when entering a level overview/mode and stays stale after returning to world map. |
| `8049D94D` | selected/entered stage index | Normal worlds: `0=L1`, ..., `9=L10`, `10=L11`; W7/A-C only use `0-9`; Wii Balance Board: `0-99`. |
| `8049D95D` | difficulty index A | `0=Easy`, `1=Normal`, `2=Hard`; defaults to `1` in difficulty selection / save-slot contexts; also reads `1` during Wii Balance Board levels, so it cannot distinguish BB mode. |
| `804E0DF8` | difficulty index B | `0=Easy`, `1=Normal`, `2=Hard`; remains last selected difficulty on difficulty select; defaults to `2` on save-slot selection; also not enough to identify Wii Balance Board levels. |
| `804E0DF9` | hovered world on world map | Same world values as `8049D945`, plus `10=Anthony's House`; this is a world-map hover/selection indicator, not a complete screen-state by itself. |
| `8049D99F` | selected save slot index | `0=Slot 1`, `1=Slot 2`, `2=Slot 3`; useful for AP safety warnings / “only write when Slot 3 is selected” heuristics. |

Recommended constants:

```python
CURRENT_WORLD_OR_MODE_INDEX = 0x8049D945
SELECTED_STAGE_INDEX = 0x8049D94D
DIFFICULTY_A = 0x8049D95D
DIFFICULTY_B = 0x804E0DF8
HOVERED_WORLD_MAP_WORLD = 0x804E0DF9
SELECTED_SAVE_SLOT = 0x8049D99F

BALANCE_BOARD_MODE_INDEX = 14
AP_SAVE_SLOT_INDEX = 2  # Slot 3

DIFFICULTY_NAMES = {0: "Easy", 1: "Normal", 2: "Hard"}
WORLD_NAMES = {
    0: "W1", 1: "W2", 2: "W3", 3: "W4", 4: "W5", 5: "W6", 6: "W7",
    7: "WA", 8: "WB", 9: "WC",
}
```

Recommended difficulty handling:

```python
def read_current_difficulty():
    a = read_u8(DIFFICULTY_A)
    b = read_u8(DIFFICULTY_B)

    if a == b and a in (0, 1, 2):
        return a

    # In actual non-BB levels this should rarely/never happen.
    # Prefer 8049D95D because it is near the other entered-stage indices.
    if a in (0, 1, 2):
        log(f"WARNING: difficulty mismatch: 8049D95D={a}, 804E0DF8={b}; using 8049D95D")
        return a
    if b in (0, 1, 2):
        log(f"WARNING: invalid DIFFICULTY_A={a}, using DIFFICULTY_B={b}")
        return b

    return None
```

Recommended stage snapshot logic:

```python
def selected_ap_slot():
    return read_u8(SELECTED_SAVE_SLOT) == AP_SAVE_SLOT_INDEX


def snapshot_entered_stage():
    mode = read_u8(CURRENT_WORLD_OR_MODE_INDEX)
    stage_idx = read_u8(SELECTED_STAGE_INDEX)

    # Wii Balance Board mode is identified by 8049D945 == 14.
    # Difficulty reads as Normal/1 here, so do not use difficulty to classify BB levels.
    if mode == BALANCE_BOARD_MODE_INDEX:
        return {
            "kind": "balance_board",
            "index": stage_idx,  # 0-99
        }

    return {
        "kind": "normal_or_bonus",
        "difficulty": read_current_difficulty(),
        "world_index": mode,
        "level_index": stage_idx,
    }
```

Safety note:
- `8049D99F` is useful to warn/refuse writes when the selected UI save slot is not Slot 3.
- Do not use it as the only authority for the active loaded save block until save-slot load behavior is fully understood.
- A conservative client can refuse AP writes when `8049D99F != 2` in save-file selection/menu contexts.

### Combined in-level detector

A DME scan produced 146 candidate byte addresses that changed `0 -> 1` when entering a level. After filtering dirty/non-binary and in-level flicker candidates, 137 addresses remained clean and stable across the test runs.

Confirmed bad/blacklisted candidates:

```python
IN_LEVEL_BAD_CANDIDATES = {
    0x80477960,  # became 0x30
    0x80488161,  # briefly 0xFF
    0x804881B5,  # briefly 0xFF
    0x8048D2BB,  # binary, but long in-level zero periods
    0x80527749,  # flickered to 0x02
    0x806C9044,  # binary, but in-level drops to 0
    0x806C9048,  # binary, but frequent in-level drops to 0
    0x8079759B,  # briefly 0xA8
    0x80CBD5E3,  # non-binary values 0x11, 0x1C, 0x62, 0x6F
}
```

Stable candidates:

```python
IN_LEVEL_CANDIDATES = [
    0x80486D59, 0x80486D5F, 0x80486D61, 0x804881AF,
    0x80488203, 0x804E764B, 0x806C30E7, 0x806C3171,
    0x806C3181, 0x806C903B, 0x806C903C, 0x806C905B,
    0x80CBD565, 0x80CBD5BB, 0x80D1E305, 0x80D7F085,
    0x80ED9E85, 0x80ED9EE5, 0x90458F25, 0x90458F85,
    0x90459025, 0x904590E5, 0x904591E5, 0x90459305,
    0x90459485, 0x90459645, 0x904596C5, 0x90459725,
    0x904597A5, 0x90459805, 0x90459885, 0x904598E5,
    0x90459965, 0x904599C5, 0x90459A45, 0x90459AA5,
    0x90459B25, 0x90459B85, 0x90459C05, 0x90459C65,
    0x90459CE5, 0x90459D45, 0x90459DC5, 0x90B2C414,
    0x90B2C419, 0x90B2C41E, 0x90B2C428, 0x90B2C446,
    0x90B2C448, 0x90B2C479, 0x90B2C484, 0x90B2C4FE,
    0x90B2C50A, 0x90B2C50E, 0x90B2C512, 0x90B2C516,
    0x90B2C60E, 0x90B2C70A, 0x90B2C80A, 0x90B2C882,
    0x90B2C96A, 0x90B2CB54, 0x90B2CB55, 0x90B2CB62,
    0x90B2CB6A, 0x90B2CB6C, 0x90B2CB6D, 0x90B2CB72,
    0x90B2CB74, 0x90B2CB75, 0x90B2CB7A, 0x90B2CB7C,
    0x90B2CB7D, 0x90B2CB82, 0x90B2CB9C, 0x90B2CBA4,
    0x90B2CBA5, 0x90B2CBAC, 0x90B2CBAD, 0x90B2CBCC,
    0x90B2CBCD, 0x90B2CBD4, 0x90B2CBD5, 0x90B2CBDC,
    0x90B2CBDD, 0x90B2CBFC, 0x90B2CBFD, 0x90B2CC04,
    0x90B2CC0C, 0x90B2CC0D, 0x90B2CC2C, 0x90B2CC2D,
    0x90B2CC34, 0x90B2CC35, 0x90B2CC3C, 0x90B2CC3D,
    0x90B2D050, 0x90B2D051, 0x90B2D058, 0x90B2D059,
    0x90B2D068, 0x90B2D069, 0x90B2D070, 0x90B2D071,
    0x90B2D080, 0x90B2DD24, 0x90B66EAB, 0x90B80A3F,
    0x90B8B5A3, 0x90B9A677, 0x90B9B7EE, 0x90BAFD8D,
    0x90BB06BA, 0x90BC7B9A, 0x90BC9529, 0x90BC98FE,
    0x90BC9DF3, 0x90BC9EEE, 0x90BCC9A3, 0x90BD0222,
    0x90BD03C9, 0x90BD67FB, 0x90BE8BC7, 0x90BE8CF5,
    0x90BE9357, 0x90BE939D, 0x90BE94A1, 0x90BE9519,
    0x90C07CAD, 0x90C088A1, 0x90CA1893, 0x90D3708C,
    0x90D5AA0F, 0x90EA76F4, 0x90EEB6F4, 0x90F0C02D,
    0x91F2BA29,
]
```

Use them as a combined majority/hysteresis detector rather than relying on a single address.

```python
IN_LEVEL_ENTER_THRESHOLD = 100  # out of 137 stable candidates
IN_LEVEL_EXIT_THRESHOLD = 30


def get_in_level_score():
    return sum(1 for addr in IN_LEVEL_CANDIDATES if read_u8(addr) == 1)


def update_in_level_state(previous_in_level):
    score = get_in_level_score()

    if not previous_in_level and score >= IN_LEVEL_ENTER_THRESHOLD:
        return True, score

    if previous_in_level and score <= IN_LEVEL_EXIT_THRESHOLD:
        return False, score

    return previous_in_level, score
```

Recommended event handling:

```python
was_in_level = False
current_stage_snapshot = None


def tick():
    global was_in_level, current_stage_snapshot

    in_level, score = update_in_level_state(was_in_level)

    if not was_in_level and in_level:
        current_stage_snapshot = snapshot_entered_stage()
        on_enter_level(current_stage_snapshot)

    if was_in_level and not in_level:
        on_exit_level(current_stage_snapshot)
        current_stage_snapshot = None

    was_in_level = in_level
```

Use cases:
- Marble popup guard while in-level / level result transitions.
- Snapshot exact level identity for indirect junk reward checks.
- Avoid dangerous L11/vehicle cleanup writes while the player is inside a level.
- Sync Mirror/Normal results only on level-exit / post-level transitions, not every frame.

### Transient goal-reached detector

A separate scan found candidate byte addresses that become `1` when the player has reached/is in the goal and reset to `0` when the player is not in the goal.

Observed reset behavior:
- The candidates become `1` when in the goal.
- They return to `0` when leaving the level.
- They return to `0` on level restart / new attempt.
- This makes them useful as transient per-attempt goal flags, especially for Wii Balance Board stages whose vanilla completion flags do not save without a physical Wii Balance Board.

Current valid goal-reached candidates:

```python
GOAL_REACHED_CANDIDATES = [
    0x90144168,
    0x901441AC,
    0x901441F0,
    0x90144234,
    0x90144278,
    0x901442BC,
    0x90144300,
    0x90144344,
    0x90144388,
    0x901443CC,
    0x90144410,
    0x90144454,
    0x90144498,
    0x901444DC,
    0x90144520,
    0x90144564,
    0x901445A8,
    0x901445EC,
    0x90144630,
    0x90459ED3,
    0x90459ED7,
]
```

Removed false/unstable candidates:

```python
REMOVED_GOAL_CANDIDATES = [
    0x9015DEAE,
    0x902ACA4E,
    0x902B0257,
    0x902B0258,
]
```

Reason for removal:
- They originally appeared in a goal-candidate scan, but later testing showed they fall out for normal levels and also no longer become `1` in Wii Balance Board levels.
- Do not include them in the AP detector.

Recommended detector:

```python
GOAL_ENTER_THRESHOLD = 5
GOAL_EXIT_THRESHOLD = 1

goal_reached_latched = False


def goal_active_count():
    return sum(1 for addr in GOAL_REACHED_CANDIDATES if read_u8(addr) == 1)


def update_goal_reached():
    global goal_reached_latched

    count = goal_active_count()

    if not goal_reached_latched and count >= GOAL_ENTER_THRESHOLD:
        goal_reached_latched = True
    elif goal_reached_latched and count <= GOAL_EXIT_THRESHOLD:
        goal_reached_latched = False

    return goal_reached_latched
```

Recommended per-attempt latch:

```python
current_stage_snapshot = None
goal_reached_this_attempt = False


def on_enter_level(stage):
    global current_stage_snapshot, goal_reached_this_attempt, goal_reached_latched
    current_stage_snapshot = stage
    goal_reached_this_attempt = False
    goal_reached_latched = False


def on_level_tick():
    global goal_reached_this_attempt
    if update_goal_reached():
        goal_reached_this_attempt = True


def on_exit_level():
    global current_stage_snapshot, goal_reached_this_attempt, goal_reached_latched

    if current_stage_snapshot and current_stage_snapshot.get("kind") == "balance_board":
        if goal_reached_this_attempt:
            index = current_stage_snapshot["index"]
            send_location_check(f"Wii Balance Board Level {index + 1}")

    current_stage_snapshot = None
    goal_reached_this_attempt = False
    goal_reached_latched = False
```

Current AP client additions:
- This transient detector is the preferred normal-level and Wii Balance Board goal detector when the game actually enters a goal/result state.
- L11 levels are a special case: the game can award the trophy and immediately leave the level, so the transient goal candidate group may never become visible long enough for AP polling.
- `0x8048D1B5` is used as a Stage Cleared fallback when it reaches `94` / `95`.
- L11 Trophy fallback is also used: if an L11 Trophy check is observed, the matching L11 Goal location is sent at the same time.
- Do not use L11 `State=3` alone as the AP Goal detector because AP may temporarily set W1L11 `State=3` for Junk Factory visibility.

### Wii Balance Board levels / AP checks

New key finding:
- `8049D945 == 14` on Wii Balance Board level select and inside Wii Balance Board levels.
- `8049D94D` stores the Wii Balance Board level index `0-99`.
- Difficulty addresses still read as `1`/Normal during Wii Balance Board levels, so difficulty cannot distinguish this mode.

Wii Balance Board level properties currently observed:
- They appear to have no Green Gem / Stump / Ant-style collectible checks.
- Their vanilla completion flag is only set when completed with a Wii Balance Board.
- Therefore a no-board AP client should not depend on vanilla BB completion flags.

AP detection approach:

```text
8049D945 == 14
+ 8049D94D == 0-99
+ transient goal-reached detector latched during that attempt
= send Wii Balance Board Level X check
```

Recommended classification:

```python
def classify_stage_snapshot():
    mode = read_u8(CURRENT_WORLD_OR_MODE_INDEX)
    stage_idx = read_u8(SELECTED_STAGE_INDEX)

    if mode == BALANCE_BOARD_MODE_INDEX:
        return {"kind": "balance_board", "index": stage_idx}

    return {
        "kind": "normal_or_bonus",
        "difficulty": read_current_difficulty(),
        "world_index": mode,
        "level_index": stage_idx,
    }
```

AP design options:
- Include Wii Balance Board levels as an optional check category.
- If enabled, use the transient goal detector rather than vanilla completion flags.
- If the player actually uses a Wii Balance Board, direct completion flags may be mapped later as an additional/backup source.

Open tasks:
- Stability-test the goal candidates across more normal levels, Wii Balance Board stages, deaths, retries, result screens, and menus.
- Confirm whether `GOAL_ENTER_THRESHOLD = 5` is conservative enough, or whether a higher threshold based on the 19 stride candidates is safer.
- Map direct Wii Balance Board completion flags if possible, but do not require them for no-board AP checks.

### L11 extra completion/reward flags

Additional per-L11 flags were found at `State + 0x15` / `Trophy + 0x09`.

Confirmed examples:

| Level | State | Trophy | Extra flag | Observation |
|---|---:|---:|---:|---|
| W1L11 | `804CE1F8` | `804CE204` | `804CE20D` | Set to `1` on real W1L11 completion only when W1L11 State was not already `3`. Does not control Junk Factory visibility. |
| W2L11 | `804CE95C` | `804CE968` | `804CE971` | Set to `1` on W2L11 completion. Does not appear to control the corresponding cutscene/progression directly. |

Predicted from the same structure:

| Level | State | Trophy | Predicted extra flag |
|---|---:|---:|---:|
| W3L11 | `804CF0C0` | `804CF0CC` | `804CF0D5` |
| W4L11 | `804CF824` | `804CF830` | `804CF839` |
| W5L11 | `804CFF88` | `804CFF94` | `804CFF9D` |
| W6L11 | `804D06EC` | `804D06F8` | `804D0701` |

Important caveat:
- `804CE20D` is not a clean W1L11 completion detector if W1L11 State was already forced to `3` for Junk Factory access. In that case, real completion can fail to set the extra flag.
- Therefore AP completion detection should not rely only on the L11 State or only on these extra flags.
- For L11 completion detection, prefer a combination of AP-side shadow state, real completion events, Trophy/extra flags where useful, and/or the observed next-world L1-L5 unlock batch.

### Junk Factory / W1L11 special case

Observed:
- Junk Factory visibility appears to depend directly on W1L11 State being `3`.
- No separate persistent Junk Factory visibility flag was found when toggling W1L11 State between `2` and `3`.
- For W1L11, Junk Factory is visible when W1L11 State is `3`; with W1L11 State `0-2`, it is not visible.
- Manually setting W1L11 State to `3` can make Junk Factory appear, but does not itself trigger the real W1L11 completion unlock batch for W2 L1-L5.

Desired AP design:
- `W1L11 Completion` remains an AP location.
- `Junk Factory Access` remains a separate AP item.
- `W2 Access` remains a separate AP item.
- Therefore `W1L11 State == 3` must not automatically mean W1L11 was completed in AP logic.

Updated rule after the yellow-context hypothesis was invalidated:
- Do not use the old yellow-crystal value to decide when to show/hide Junk Factory.
- Prefer using a real screen-state later if one is found.
- Until then, avoid aggressive W1L11 State toggling unless it is tied to a safe event/transition such as outside-level enforcement and a known menu state.
- If a temporary W1L11 `State=3` write is needed for AP-granted Junk Factory Access, treat it as a physical RAM switch only, not AP truth.

### General L11 State policy after reliable in-level detection

The combined in-level detector allows a safer policy than the old yellow-value gating.

High-level rule:
- While `in_level == True`: do not perform aggressive L11 or vehicle cleanup writes.
- On outside-level / transition cleanup: suppress only unsafe vanilla side effects that AP logic has not granted.
- On the world map, if any W1-W6 L11 State is `3`, reset it to `0` unless the client is in a specifically allowed temporary context.
- For AP-granted Junk Factory Access, only W1L11 may be temporarily raised to `3`, and only while entering/inside Anthony's House or Junk Factory.
- `8049D96F == 35` is currently used as an early Anthony's House entry context, because the hub-screen byte can update too late.
- L11 completion checks should be based on Trophy / known completion side effects / AP-side shadow state, not `State == 3` alone.

Recommended cautious policy:

```python
L11_STATES = {
    "W1L11": 0x804CE1F8,
    "W2L11": 0x804CE95C,
    "W3L11": 0x804CF0C0,
    "W4L11": 0x804CF824,
    "W5L11": 0x804CFF88,
    "W6L11": 0x804D06EC,
}


def enforce_l11_state_safe(name, state_addr, in_level):
    if in_level:
        # Do not mutate L11 state during active gameplay/result transitions.
        return

    done = ap_location_checked(f"{name} Completion")
    has_world = has_world_access_for_l11(name)

    if on_world_map() and read_u8(state_addr) == 3:
        # L11 State 3 is an event switch on the world map.
        # AP should not leave it active there unless a specific safe context needs it.
        write_u8(state_addr, 0)
        return

    if not has_world:
        # Inaccessible-world L11 states can create unsafe/crashy world states.
        if read_u8(state_addr) in (1,):
            write_u8(state_addr, 0)
        return

    if done:
        # Completion is AP-owned; State 3 may be allowed when it is needed for UI,
        # but leaving State 3 active everywhere can trigger vanilla progression behavior.
        # Until a real screen-state is found, prefer conservative cleanup only.
        pass
```

Open task:
- Find a real screen/menu state for Level Select, World Map, and Anthony's House if more precise L11 UI gating is needed.

### Suppressing vanilla next-world unlocks

Real L11 completion can unlock the first five levels of the next world. In AP, this must be treated as a vanilla side effect and undone unless the corresponding AP World Access item has been received.

Start-level groups:

```python
W2_START_LEVELS = [
    0x804CE2A4,  # W2 L1
    0x804CE350,  # W2 L2
    0x804CE3FC,  # W2 L3
    0x804CE4A8,  # W2 L4
    0x804CE554,  # W2 L5
]

W5_START_LEVELS = [
    0x804CF8D0,  # W5 L1
    0x804CF97C,  # W5 L2
    0x804CFA28,  # W5 L3
    0x804CFAD4,  # W5 L4
    0x804CFB80,  # W5 L5
]

W6_START_LEVELS = [
    0x804D0034,  # W6 L1
    0x804D00E0,  # W6 L2
    0x804D018C,  # W6 L3
    0x804D0238,  # W6 L4
    0x804D02E4,  # W6 L5
]

W7_START_LEVELS = [
    0x804D0798,  # W7 L1
    0x804D0844,  # W7 L2
    0x804D08F0,  # W7 L3
    0x804D099C,  # W7 L4
    0x804D0A48,  # W7 L5
]
```

Cleanup rule:

```python
def suppress_fresh_level_unlocks(level_addrs, access_item):
    if has_ap_item(access_item):
        return

    for addr in level_addrs:
        # Only remove fresh vanilla unlocks.
        # Do not lower played/completed states.
        if read_u8(addr) == 1:
            write_u8(addr, 0)
```

### Dangerous / special L11 candidates

All L11s should be context-gated, but these remain especially important because they interact with larger vanilla progression or vehicle requirements:

| Level | State | Trophy | Concern |
|---|---:|---:|---|
| W1L11 | `804CE1F8` | `804CE204` | Controls Junk Factory visibility and real completion can unlock W2 L1-L5. |
| W4L11 | `804CF824` | `804CF830` | Interacts with W5/Submarine progression. |
| W5L11 | `804CFF88` | `804CFF94` | Interacts with W6/Rocket Ship progression. |
| W6L11 | `804D06EC` | `804D06F8` | Likely interacts with later progression. |

---
## 5. Level Record Structure

### Stable structural constants

```text
Level stride              = 0xAC
Normal world block stride = 11 * 0xAC = 0x764
A-C bonus block stride    = 10 * 0xAC = 0x6B8
```

### Green Gem / Stump Temple Piece flag structure

Original byte formula is still useful for the canonical game-written bytes:

```text
State  = Trophy - 0x0C
Green byte  = Trophy - 0x05
Stump byte  = Trophy - 0x01
Trophy = Trophy
```

Updated interpretation:
- Green and Stump are likely 32-bit nonzero flags.
- Wii/PPC big-endian `u32(1)` appears as `00 00 00 01`, so the game normally changes the last byte.
- Display/counter logic appears to check whether the whole u32 flag is nonzero.

Recommended notation:

```text
State  = Trophy - 0x0C
Green  = u32 block Trophy - 0x08 through Trophy - 0x05
Stump  = u32 block Trophy - 0x04 through Trophy - 0x01
Trophy = Trophy

Canonical byte addresses:
Green byte = Trophy - 0x05
Stump byte = Trophy - 0x01
```

Example W6L1:

```text
State      = 804D0034
Green u32  = 804D0038-804D003B
Green byte = 804D003B, game-written byte
Stump u32  = 804D003C-804D003F
Stump byte = 804D003F, game-written byte
Trophy     = 804D0040
```

Manual tests:
- Setting any byte in `804D0038-804D003B` nonzero can make W6L1 Green Gem display as collected.
- Setting any byte in `804D003C-804D003F` nonzero can make W6L1 Stump Temple Piece display as collected.
- The game normally writes the canonical last byte.
- Changing a Stump flag immediately increases the total Stump counter without needing a UI reload.

AP check implication:
- Use canonical game-written byte addresses for simple byte-based checks.
- Or read the full u32 block as nonzero for robustness.
- Do not treat every byte in a u32 block as a separate collectible.


### Difficulty-specific record structures

Normal / Easy direct collectible structure:

```text
State  = Trophy - 0x0C
Green  = Trophy - 0x05  # canonical game-written byte of Green u32 block
Stump  = Trophy - 0x01  # canonical game-written byte of Stump u32 block
Trophy = Trophy
Best time = Trophy + 0x06, u16 big-endian milliseconds
```

Hard structure:

```text
State  = Trophy - 0x0C
Ant    = Trophy - 0x05
Trophy = Trophy
Best time = Trophy + 0x06, u16 big-endian milliseconds
```

Hard notes:
- Hard mode has no Green Gems.
- Hard mode Stump Temple Piece pickups are not stored as persistent collectible flags.
- Hard Stump-style pickups only grant junk items. Detect these as AP locations indirectly by comparing expected junk-item count deltas while the exact current level is known.
- Confirmed Hard W1L1: State `804D0EFC`, Ant `804D0F03`, Trophy `804D0F08`.

### Best time format

Best times appear to be stored as big-endian u16 milliseconds at `Trophy + 0x06`.

Confirmed Normal W1L2 examples:

| Best time | Bytes | u16 | Meaning |
|---:|---:|---:|---:|
| 17.33s | `804CDBFE=67`, `804CDBFF=181` | `0x43B5` | 17333 ms |
| 10.21s | `804CDBFE=39`, `804CDBFF=232` | `0x27E8` | 10216 ms |
| 6.63s | `804CDBFE=25`, `804CDBFF=233` | `0x19E9` | 6633 ms |

Helper:

```python
def read_u16_be(addr):
    return (read_u8(addr) << 8) | read_u8(addr + 1)


def write_u16_be(addr, value):
    value = max(0, min(value, 0xFFFF))
    write_u8(addr, (value >> 8) & 0xFF)
    write_u8(addr + 1, value & 0xFF)


def read_best_time_ms(trophy_addr):
    return read_u16_be(trophy_addr + 0x06)


def write_best_time_ms(trophy_addr, ms):
    write_u16_be(trophy_addr + 0x06, ms)
```

---
## 6. Level Address Tables

Notes for tables below:
- Green Gem and Stump Temple Piece columns list the canonical game-written byte addresses.
- Conceptually these are the last byte of the u32 blocks described above.
- W1-W4 are confirmed by testing.
- W5-W7 are predicted from the same stride unless later confirmed.
- W7 has no Stump Pieces.
- L11 bonus levels have no Green/Stump.
- W7 has no L11.

### Normal W1-W7 tables

Notes:
- W1-W4 are confirmed by testing.
- W5-W7 are predicted from the same stride unless later confirmed.
- W7 has no Stump Pieces.
- L11 bonus levels have no Green/Stump.
- W7 has no L11.

### W1 (confirmed)

| Level | State | Green Gem | Stump Temple Piece | Trophy | Notes |
|---:|---:|---:|---:|---:|---|
| L1 | `804CDB40` | `804CDB47` | `804CDB4B` | `804CDB4C` |  |
| L2 | `804CDBEC` | `804CDBF3` | `804CDBF7` | `804CDBF8` |  |
| L3 | `804CDC98` | `804CDC9F` | `804CDCA3` | `804CDCA4` |  |
| L4 | `804CDD44` | `804CDD4B` | `804CDD4F` | `804CDD50` |  |
| L5 | `804CDDF0` | `804CDDF7` | `804CDDFB` | `804CDDFC` |  |
| L6 | `804CDE9C` | `804CDEA3` | `804CDEA7` | `804CDEA8` |  |
| L7 | `804CDF48` | `804CDF4F` | `804CDF53` | `804CDF54` |  |
| L8 | `804CDFF4` | `804CDFFB` | `804CDFFF` | `804CE000` |  |
| L9 | `804CE0A0` | `804CE0A7` | `804CE0AB` | `804CE0AC` |  |
| L10 | `804CE14C` | `804CE153` | `804CE157` | `804CE158` |  |
| L11 | `804CE1F8` | — | — | `804CE204` | bonus/Level 11-style; no Green/Stump |

### W2 (confirmed)

| Level | State | Green Gem | Stump Temple Piece | Trophy | Notes |
|---:|---:|---:|---:|---:|---|
| L1 | `804CE2A4` | `804CE2AB` | `804CE2AF` | `804CE2B0` |  |
| L2 | `804CE350` | `804CE357` | `804CE35B` | `804CE35C` |  |
| L3 | `804CE3FC` | `804CE403` | `804CE407` | `804CE408` |  |
| L4 | `804CE4A8` | `804CE4AF` | `804CE4B3` | `804CE4B4` |  |
| L5 | `804CE554` | `804CE55B` | `804CE55F` | `804CE560` |  |
| L6 | `804CE600` | `804CE607` | `804CE60B` | `804CE60C` |  |
| L7 | `804CE6AC` | `804CE6B3` | `804CE6B7` | `804CE6B8` |  |
| L8 | `804CE758` | `804CE75F` | `804CE763` | `804CE764` |  |
| L9 | `804CE804` | `804CE80B` | `804CE80F` | `804CE810` |  |
| L10 | `804CE8B0` | `804CE8B7` | `804CE8BB` | `804CE8BC` |  |
| L11 | `804CE95C` | — | — | `804CE968` | bonus/Level 11-style; no Green/Stump |

### W3 (confirmed)

| Level | State | Green Gem | Stump Temple Piece | Trophy | Notes |
|---:|---:|---:|---:|---:|---|
| L1 | `804CEA08` | `804CEA0F` | `804CEA13` | `804CEA14` |  |
| L2 | `804CEAB4` | `804CEABB` | `804CEABF` | `804CEAC0` |  |
| L3 | `804CEB60` | `804CEB67` | `804CEB6B` | `804CEB6C` |  |
| L4 | `804CEC0C` | `804CEC13` | `804CEC17` | `804CEC18` |  |
| L5 | `804CECB8` | `804CECBF` | `804CECC3` | `804CECC4` |  |
| L6 | `804CED64` | `804CED6B` | `804CED6F` | `804CED70` |  |
| L7 | `804CEE10` | `804CEE17` | `804CEE1B` | `804CEE1C` |  |
| L8 | `804CEEBC` | `804CEEC3` | `804CEEC7` | `804CEEC8` |  |
| L9 | `804CEF68` | `804CEF6F` | `804CEF73` | `804CEF74` |  |
| L10 | `804CF014` | `804CF01B` | `804CF01F` | `804CF020` |  |
| L11 | `804CF0C0` | — | — | `804CF0CC` | bonus/Level 11-style; no Green/Stump |

### W4 (confirmed)

| Level | State | Green Gem | Stump Temple Piece | Trophy | Notes |
|---:|---:|---:|---:|---:|---|
| L1 | `804CF16C` | `804CF173` | `804CF177` | `804CF178` |  |
| L2 | `804CF218` | `804CF21F` | `804CF223` | `804CF224` |  |
| L3 | `804CF2C4` | `804CF2CB` | `804CF2CF` | `804CF2D0` |  |
| L4 | `804CF370` | `804CF377` | `804CF37B` | `804CF37C` |  |
| L5 | `804CF41C` | `804CF423` | `804CF427` | `804CF428` |  |
| L6 | `804CF4C8` | `804CF4CF` | `804CF4D3` | `804CF4D4` |  |
| L7 | `804CF574` | `804CF57B` | `804CF57F` | `804CF580` |  |
| L8 | `804CF620` | `804CF627` | `804CF62B` | `804CF62C` |  |
| L9 | `804CF6CC` | `804CF6D3` | `804CF6D7` | `804CF6D8` |  |
| L10 | `804CF778` | `804CF77F` | `804CF783` | `804CF784` |  |
| L11 | `804CF824` | — | — | `804CF830` | bonus/Level 11-style; no Green/Stump |

### W5 (predicted / needs confirmation)

| Level | State | Green Gem | Stump Temple Piece | Trophy | Notes |
|---:|---:|---:|---:|---:|---|
| L1 | `804CF8D0` | `804CF8D7` | `804CF8DB` | `804CF8DC` |  |
| L2 | `804CF97C` | `804CF983` | `804CF987` | `804CF988` |  |
| L3 | `804CFA28` | `804CFA2F` | `804CFA33` | `804CFA34` |  |
| L4 | `804CFAD4` | `804CFADB` | `804CFADF` | `804CFAE0` |  |
| L5 | `804CFB80` | `804CFB87` | `804CFB8B` | `804CFB8C` |  |
| L6 | `804CFC2C` | `804CFC33` | `804CFC37` | `804CFC38` |  |
| L7 | `804CFCD8` | `804CFCDF` | `804CFCE3` | `804CFCE4` |  |
| L8 | `804CFD84` | `804CFD8B` | `804CFD8F` | `804CFD90` |  |
| L9 | `804CFE30` | `804CFE37` | `804CFE3B` | `804CFE3C` |  |
| L10 | `804CFEDC` | `804CFEE3` | `804CFEE7` | `804CFEE8` |  |
| L11 | `804CFF88` | — | — | `804CFF94` | bonus/Level 11-style; no Green/Stump |

### W6 (predicted / needs confirmation)

| Level | State | Green Gem | Stump Temple Piece | Trophy | Notes |
|---:|---:|---:|---:|---:|---|
| L1 | `804D0034` | `804D003B` | `804D003F` | `804D0040` |  |
| L2 | `804D00E0` | `804D00E7` | `804D00EB` | `804D00EC` |  |
| L3 | `804D018C` | `804D0193` | `804D0197` | `804D0198` |  |
| L4 | `804D0238` | `804D023F` | `804D0243` | `804D0244` |  |
| L5 | `804D02E4` | `804D02EB` | `804D02EF` | `804D02F0` |  |
| L6 | `804D0390` | `804D0397` | `804D039B` | `804D039C` |  |
| L7 | `804D043C` | `804D0443` | `804D0447` | `804D0448` |  |
| L8 | `804D04E8` | `804D04EF` | `804D04F3` | `804D04F4` |  |
| L9 | `804D0594` | `804D059B` | `804D059F` | `804D05A0` |  |
| L10 | `804D0640` | `804D0647` | `804D064B` | `804D064C` |  |
| L11 | `804D06EC` | — | — | `804D06F8` | bonus/Level 11-style; no Green/Stump |

### W7 (predicted / needs confirmation)

| Level | State | Green Gem | Stump Temple Piece | Trophy | Notes |
|---:|---:|---:|---:|---:|---|
| L1 | `804D0798` | `804D079F` | — | `804D07A4` | Stump Temple world; no Stump Pieces |
| L2 | `804D0844` | `804D084B` | — | `804D0850` | Stump Temple world; no Stump Pieces |
| L3 | `804D08F0` | `804D08F7` | — | `804D08FC` | Stump Temple world; no Stump Pieces |
| L4 | `804D099C` | `804D09A3` | — | `804D09A8` | Stump Temple world; no Stump Pieces |
| L5 | `804D0A48` | `804D0A4F` | — | `804D0A54` | Stump Temple world; no Stump Pieces |
| L6 | `804D0AF4` | `804D0AFB` | — | `804D0B00` | Stump Temple world; no Stump Pieces |
| L7 | `804D0BA0` | `804D0BA7` | — | `804D0BAC` | Stump Temple world; no Stump Pieces |
| L8 | `804D0C4C` | `804D0C53` | — | `804D0C58` | Stump Temple world; no Stump Pieces |
| L9 | `804D0CF8` | `804D0CFF` | — | `804D0D04` | Stump Temple world; no Stump Pieces |
| L10 | `804D0DA4` | `804D0DAB` | — | `804D0DB0` | Stump Temple world; no Stump Pieces |


### Easy W1-W7 tables (predicted from Easy W1L2 normal-slot Trophy)

Status:
- Easy W1L2 normal/non-Mirror Trophy `804CA83C` was observed directly.
- Easy W1L1 Trophy anchor is inferred as `804CA790` by subtracting one level stride (`0xAC`).
- Remaining Easy tables are predicted using the same `0xAC` level stride and `0x764` world stride unless later confirmed.
- Easy appears to use the Normal-style direct Green/Stump collectible structure, but individual Easy addresses still need confirmation.

#### Easy W1 (predicted)

| Level | State | Green Gem | Stump Temple Piece | Trophy | Notes |
|---:|---:|---:|---:|---:|---|
| L1 | `804CA784` | `804CA78B` | `804CA78F` | `804CA790` | predicted |
| L2 | `804CA830` | `804CA837` | `804CA83B` | `804CA83C` | Trophy observed; State/Green/Stump predicted from structure |
| L3 | `804CA8DC` | `804CA8E3` | `804CA8E7` | `804CA8E8` | predicted |
| L4 | `804CA988` | `804CA98F` | `804CA993` | `804CA994` | predicted |
| L5 | `804CAA34` | `804CAA3B` | `804CAA3F` | `804CAA40` | predicted |
| L6 | `804CAAE0` | `804CAAE7` | `804CAAEB` | `804CAAEC` | predicted |
| L7 | `804CAB8C` | `804CAB93` | `804CAB97` | `804CAB98` | predicted |
| L8 | `804CAC38` | `804CAC3F` | `804CAC43` | `804CAC44` | predicted |
| L9 | `804CACE4` | `804CACEB` | `804CACEF` | `804CACF0` | predicted |
| L10 | `804CAD90` | `804CAD97` | `804CAD9B` | `804CAD9C` | predicted |
| L11 | `804CAE3C` | — | — | `804CAE48` | bonus/Level 11-style; no Green/Stump; predicted |

#### Easy W2 (predicted)

| Level | State | Green Gem | Stump Temple Piece | Trophy | Notes |
|---:|---:|---:|---:|---:|---|
| L1 | `804CAEE8` | `804CAEEF` | `804CAEF3` | `804CAEF4` | predicted |
| L2 | `804CAF94` | `804CAF9B` | `804CAF9F` | `804CAFA0` | predicted |
| L3 | `804CB040` | `804CB047` | `804CB04B` | `804CB04C` | predicted |
| L4 | `804CB0EC` | `804CB0F3` | `804CB0F7` | `804CB0F8` | predicted |
| L5 | `804CB198` | `804CB19F` | `804CB1A3` | `804CB1A4` | predicted |
| L6 | `804CB244` | `804CB24B` | `804CB24F` | `804CB250` | predicted |
| L7 | `804CB2F0` | `804CB2F7` | `804CB2FB` | `804CB2FC` | predicted |
| L8 | `804CB39C` | `804CB3A3` | `804CB3A7` | `804CB3A8` | predicted |
| L9 | `804CB448` | `804CB44F` | `804CB453` | `804CB454` | predicted |
| L10 | `804CB4F4` | `804CB4FB` | `804CB4FF` | `804CB500` | predicted |
| L11 | `804CB5A0` | — | — | `804CB5AC` | bonus/Level 11-style; no Green/Stump; predicted |

#### Easy W3 (predicted)

| Level | State | Green Gem | Stump Temple Piece | Trophy | Notes |
|---:|---:|---:|---:|---:|---|
| L1 | `804CB64C` | `804CB653` | `804CB657` | `804CB658` | predicted |
| L2 | `804CB6F8` | `804CB6FF` | `804CB703` | `804CB704` | predicted |
| L3 | `804CB7A4` | `804CB7AB` | `804CB7AF` | `804CB7B0` | predicted |
| L4 | `804CB850` | `804CB857` | `804CB85B` | `804CB85C` | predicted |
| L5 | `804CB8FC` | `804CB903` | `804CB907` | `804CB908` | predicted |
| L6 | `804CB9A8` | `804CB9AF` | `804CB9B3` | `804CB9B4` | predicted |
| L7 | `804CBA54` | `804CBA5B` | `804CBA5F` | `804CBA60` | predicted |
| L8 | `804CBB00` | `804CBB07` | `804CBB0B` | `804CBB0C` | predicted |
| L9 | `804CBBAC` | `804CBBB3` | `804CBBB7` | `804CBBB8` | predicted |
| L10 | `804CBC58` | `804CBC5F` | `804CBC63` | `804CBC64` | predicted |
| L11 | `804CBD04` | — | — | `804CBD10` | bonus/Level 11-style; no Green/Stump; predicted |

#### Easy W4 (predicted)

| Level | State | Green Gem | Stump Temple Piece | Trophy | Notes |
|---:|---:|---:|---:|---:|---|
| L1 | `804CBDB0` | `804CBDB7` | `804CBDBB` | `804CBDBC` | predicted |
| L2 | `804CBE5C` | `804CBE63` | `804CBE67` | `804CBE68` | predicted |
| L3 | `804CBF08` | `804CBF0F` | `804CBF13` | `804CBF14` | predicted |
| L4 | `804CBFB4` | `804CBFBB` | `804CBFBF` | `804CBFC0` | predicted |
| L5 | `804CC060` | `804CC067` | `804CC06B` | `804CC06C` | predicted |
| L6 | `804CC10C` | `804CC113` | `804CC117` | `804CC118` | predicted |
| L7 | `804CC1B8` | `804CC1BF` | `804CC1C3` | `804CC1C4` | predicted |
| L8 | `804CC264` | `804CC26B` | `804CC26F` | `804CC270` | predicted |
| L9 | `804CC310` | `804CC317` | `804CC31B` | `804CC31C` | predicted |
| L10 | `804CC3BC` | `804CC3C3` | `804CC3C7` | `804CC3C8` | predicted |
| L11 | `804CC468` | — | — | `804CC474` | bonus/Level 11-style; no Green/Stump; predicted |

#### Easy W5 (predicted)

| Level | State | Green Gem | Stump Temple Piece | Trophy | Notes |
|---:|---:|---:|---:|---:|---|
| L1 | `804CC514` | `804CC51B` | `804CC51F` | `804CC520` | predicted |
| L2 | `804CC5C0` | `804CC5C7` | `804CC5CB` | `804CC5CC` | predicted |
| L3 | `804CC66C` | `804CC673` | `804CC677` | `804CC678` | predicted |
| L4 | `804CC718` | `804CC71F` | `804CC723` | `804CC724` | predicted |
| L5 | `804CC7C4` | `804CC7CB` | `804CC7CF` | `804CC7D0` | predicted |
| L6 | `804CC870` | `804CC877` | `804CC87B` | `804CC87C` | predicted |
| L7 | `804CC91C` | `804CC923` | `804CC927` | `804CC928` | predicted |
| L8 | `804CC9C8` | `804CC9CF` | `804CC9D3` | `804CC9D4` | predicted |
| L9 | `804CCA74` | `804CCA7B` | `804CCA7F` | `804CCA80` | predicted |
| L10 | `804CCB20` | `804CCB27` | `804CCB2B` | `804CCB2C` | predicted |
| L11 | `804CCBCC` | — | — | `804CCBD8` | bonus/Level 11-style; no Green/Stump; predicted |

#### Easy W6 (predicted)

| Level | State | Green Gem | Stump Temple Piece | Trophy | Notes |
|---:|---:|---:|---:|---:|---|
| L1 | `804CCC78` | `804CCC7F` | `804CCC83` | `804CCC84` | predicted |
| L2 | `804CCD24` | `804CCD2B` | `804CCD2F` | `804CCD30` | predicted |
| L3 | `804CCDD0` | `804CCDD7` | `804CCDDB` | `804CCDDC` | predicted |
| L4 | `804CCE7C` | `804CCE83` | `804CCE87` | `804CCE88` | predicted |
| L5 | `804CCF28` | `804CCF2F` | `804CCF33` | `804CCF34` | predicted |
| L6 | `804CCFD4` | `804CCFDB` | `804CCFDF` | `804CCFE0` | predicted |
| L7 | `804CD080` | `804CD087` | `804CD08B` | `804CD08C` | predicted |
| L8 | `804CD12C` | `804CD133` | `804CD137` | `804CD138` | predicted |
| L9 | `804CD1D8` | `804CD1DF` | `804CD1E3` | `804CD1E4` | predicted |
| L10 | `804CD284` | `804CD28B` | `804CD28F` | `804CD290` | predicted |
| L11 | `804CD330` | — | — | `804CD33C` | bonus/Level 11-style; no Green/Stump; predicted |

#### Easy W7 (predicted)

| Level | State | Green Gem | Stump Temple Piece | Trophy | Notes |
|---:|---:|---:|---:|---:|---|
| L1 | `804CD3DC` | `804CD3E3` | — | `804CD3E8` | Stump Temple world; no Stump Pieces; predicted |
| L2 | `804CD488` | `804CD48F` | — | `804CD494` | Stump Temple world; no Stump Pieces; predicted |
| L3 | `804CD534` | `804CD53B` | — | `804CD540` | Stump Temple world; no Stump Pieces; predicted |
| L4 | `804CD5E0` | `804CD5E7` | — | `804CD5EC` | Stump Temple world; no Stump Pieces; predicted |
| L5 | `804CD68C` | `804CD693` | — | `804CD698` | Stump Temple world; no Stump Pieces; predicted |
| L6 | `804CD738` | `804CD73F` | — | `804CD744` | Stump Temple world; no Stump Pieces; predicted |
| L7 | `804CD7E4` | `804CD7EB` | — | `804CD7F0` | Stump Temple world; no Stump Pieces; predicted |
| L8 | `804CD890` | `804CD897` | — | `804CD89C` | Stump Temple world; no Stump Pieces; predicted |
| L9 | `804CD93C` | `804CD943` | — | `804CD948` | Stump Temple world; no Stump Pieces; predicted |
| L10 | `804CD9E8` | `804CD9EF` | — | `804CD9F4` | Stump Temple world; no Stump Pieces; predicted |

### Hard W1-W7 tables (predicted from confirmed Hard W1L1)

Status:
- Hard W1L1 State `804D0EFC`, Ant `804D0F03`, and Trophy `804D0F08` are confirmed.
- Hard has no Green Gems.
- Hard Stump Temple Piece pickups are not stored as persistent collectible flags; they only grant junk items.
- Therefore Hard tables use `State`, `Ant`, and `Trophy` columns only.
- Remaining Hard addresses are predicted using the same `0xAC` level stride and `0x764` world stride unless later confirmed.

#### Hard W1 (confirmed anchor / predicted rest)

| Level | State | Ant | Trophy | Notes |
|---:|---:|---:|---:|---|
| L1 | `804D0EFC` | `804D0F03` | `804D0F08` | confirmed; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L2 | `804D0FA8` | `804D0FAF` | `804D0FB4` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L3 | `804D1054` | `804D105B` | `804D1060` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L4 | `804D1100` | `804D1107` | `804D110C` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L5 | `804D11AC` | `804D11B3` | `804D11B8` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L6 | `804D1258` | `804D125F` | `804D1264` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L7 | `804D1304` | `804D130B` | `804D1310` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L8 | `804D13B0` | `804D13B7` | `804D13BC` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L9 | `804D145C` | `804D1463` | `804D1468` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L10 | `804D1508` | `804D150F` | `804D1514` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L11 | `804D15B4` | — | `804D15C0` | bonus/Level 11-style; Ant unknown/likely none; predicted |

#### Hard W2 (predicted)

| Level | State | Ant | Trophy | Notes |
|---:|---:|---:|---:|---|
| L1 | `804D1660` | `804D1667` | `804D166C` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L2 | `804D170C` | `804D1713` | `804D1718` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L3 | `804D17B8` | `804D17BF` | `804D17C4` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L4 | `804D1864` | `804D186B` | `804D1870` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L5 | `804D1910` | `804D1917` | `804D191C` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L6 | `804D19BC` | `804D19C3` | `804D19C8` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L7 | `804D1A68` | `804D1A6F` | `804D1A74` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L8 | `804D1B14` | `804D1B1B` | `804D1B20` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L9 | `804D1BC0` | `804D1BC7` | `804D1BCC` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L10 | `804D1C6C` | `804D1C73` | `804D1C78` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L11 | `804D1D18` | — | `804D1D24` | bonus/Level 11-style; Ant unknown/likely none; predicted |

#### Hard W3 (predicted)

| Level | State | Ant | Trophy | Notes |
|---:|---:|---:|---:|---|
| L1 | `804D1DC4` | `804D1DCB` | `804D1DD0` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L2 | `804D1E70` | `804D1E77` | `804D1E7C` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L3 | `804D1F1C` | `804D1F23` | `804D1F28` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L4 | `804D1FC8` | `804D1FCF` | `804D1FD4` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L5 | `804D2074` | `804D207B` | `804D2080` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L6 | `804D2120` | `804D2127` | `804D212C` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L7 | `804D21CC` | `804D21D3` | `804D21D8` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L8 | `804D2278` | `804D227F` | `804D2284` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L9 | `804D2324` | `804D232B` | `804D2330` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L10 | `804D23D0` | `804D23D7` | `804D23DC` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L11 | `804D247C` | — | `804D2488` | bonus/Level 11-style; Ant unknown/likely none; predicted |

#### Hard W4 (predicted)

| Level | State | Ant | Trophy | Notes |
|---:|---:|---:|---:|---|
| L1 | `804D2528` | `804D252F` | `804D2534` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L2 | `804D25D4` | `804D25DB` | `804D25E0` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L3 | `804D2680` | `804D2687` | `804D268C` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L4 | `804D272C` | `804D2733` | `804D2738` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L5 | `804D27D8` | `804D27DF` | `804D27E4` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L6 | `804D2884` | `804D288B` | `804D2890` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L7 | `804D2930` | `804D2937` | `804D293C` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L8 | `804D29DC` | `804D29E3` | `804D29E8` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L9 | `804D2A88` | `804D2A8F` | `804D2A94` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L10 | `804D2B34` | `804D2B3B` | `804D2B40` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L11 | `804D2BE0` | — | `804D2BEC` | bonus/Level 11-style; Ant unknown/likely none; predicted |

#### Hard W5 (predicted)

| Level | State | Ant | Trophy | Notes |
|---:|---:|---:|---:|---|
| L1 | `804D2C8C` | `804D2C93` | `804D2C98` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L2 | `804D2D38` | `804D2D3F` | `804D2D44` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L3 | `804D2DE4` | `804D2DEB` | `804D2DF0` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L4 | `804D2E90` | `804D2E97` | `804D2E9C` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L5 | `804D2F3C` | `804D2F43` | `804D2F48` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L6 | `804D2FE8` | `804D2FEF` | `804D2FF4` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L7 | `804D3094` | `804D309B` | `804D30A0` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L8 | `804D3140` | `804D3147` | `804D314C` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L9 | `804D31EC` | `804D31F3` | `804D31F8` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L10 | `804D3298` | `804D329F` | `804D32A4` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L11 | `804D3344` | — | `804D3350` | bonus/Level 11-style; Ant unknown/likely none; predicted |

#### Hard W6 (predicted)

| Level | State | Ant | Trophy | Notes |
|---:|---:|---:|---:|---|
| L1 | `804D33F0` | `804D33F7` | `804D33FC` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L2 | `804D349C` | `804D34A3` | `804D34A8` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L3 | `804D3548` | `804D354F` | `804D3554` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L4 | `804D35F4` | `804D35FB` | `804D3600` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L5 | `804D36A0` | `804D36A7` | `804D36AC` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L6 | `804D374C` | `804D3753` | `804D3758` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L7 | `804D37F8` | `804D37FF` | `804D3804` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L8 | `804D38A4` | `804D38AB` | `804D38B0` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L9 | `804D3950` | `804D3957` | `804D395C` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L10 | `804D39FC` | `804D3A03` | `804D3A08` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L11 | `804D3AA8` | — | `804D3AB4` | bonus/Level 11-style; Ant unknown/likely none; predicted |

#### Hard W7 (predicted)

| Level | State | Ant | Trophy | Notes |
|---:|---:|---:|---:|---|
| L1 | `804D3B54` | `804D3B5B` | `804D3B60` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L2 | `804D3C00` | `804D3C07` | `804D3C0C` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L3 | `804D3CAC` | `804D3CB3` | `804D3CB8` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L4 | `804D3D58` | `804D3D5F` | `804D3D64` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L5 | `804D3E04` | `804D3E0B` | `804D3E10` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L6 | `804D3EB0` | `804D3EB7` | `804D3EBC` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L7 | `804D3F5C` | `804D3F63` | `804D3F68` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L8 | `804D4008` | `804D400F` | `804D4014` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L9 | `804D40B4` | `804D40BB` | `804D40C0` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |
| L10 | `804D4160` | `804D4167` | `804D416C` | predicted; Stump-style pickup, if present, must be detected indirectly through junk increase |


### Worlds A-C State/Trophy tables

A-C:
- shared between Easy and Normal
- no Green Gems
- no Stump Pieces
- State + Trophy only

### WA (confirmed)

| Level | State | Trophy | Notes |
|---:|---:|---:|---|
| L1 | `804D42B8` | `804D42C4` | may already show completed because A-C progress is shared between Easy and Normal |
| L2 | `804D4364` | `804D4370` |  |
| L3 | `804D4410` | `804D441C` |  |
| L4 | `804D44BC` | `804D44C8` |  |
| L5 | `804D4568` | `804D4574` |  |
| L6 | `804D4614` | `804D4620` |  |
| L7 | `804D46C0` | `804D46CC` |  |
| L8 | `804D476C` | `804D4778` |  |
| L9 | `804D4818` | `804D4824` |  |
| L10 | `804D48C4` | `804D48D0` |  |

### WB (confirmed)

| Level | State | Trophy | Notes |
|---:|---:|---:|---|
| L1 | `804D4970` | `804D497C` | may already show completed because A-C progress is shared between Easy and Normal |
| L2 | `804D4A1C` | `804D4A28` |  |
| L3 | `804D4AC8` | `804D4AD4` |  |
| L4 | `804D4B74` | `804D4B80` |  |
| L5 | `804D4C20` | `804D4C2C` | may already show completed because A-C progress is shared between Easy and Normal |
| L6 | `804D4CCC` | `804D4CD8` |  |
| L7 | `804D4D78` | `804D4D84` |  |
| L8 | `804D4E24` | `804D4E30` |  |
| L9 | `804D4ED0` | `804D4EDC` |  |
| L10 | `804D4F7C` | `804D4F88` |  |


### W? unknown gap block

This block appeared where C was first predicted to be. It is not currently identified as C.

### W? (unknown/gap block)

| Level | State | Trophy | Notes |
|---:|---:|---:|---|
| L1 | `804D5028` | `804D5034` |  |
| L2 | `804D50D4` | `804D50E0` |  |
| L3 | `804D5180` | `804D518C` |  |
| L4 | `804D522C` | `804D5238` |  |
| L5 | `804D52D8` | `804D52E4` |  |
| L6 | `804D5384` | `804D5390` |  |
| L7 | `804D5430` | `804D543C` |  |
| L8 | `804D54DC` | `804D54E8` |  |
| L9 | `804D5588` | `804D5594` |  |
| L10 | `804D5634` | `804D5640` |  |


### WC (confirmed from C2 Trophy 804D5798)

| Level | State | Trophy | Notes |
|---:|---:|---:|---|
| L1 | `804D56E0` | `804D56EC` | may already show completed because A-C progress is shared between Easy and Normal |
| L2 | `804D578C` | `804D5798` |  |
| L3 | `804D5838` | `804D5844` |  |
| L4 | `804D58E4` | `804D58F0` |  |
| L5 | `804D5990` | `804D599C` | may already show completed because A-C progress is shared between Easy and Normal |
| L6 | `804D5A3C` | `804D5A48` |  |
| L7 | `804D5AE8` | `804D5AF4` |  |
| L8 | `804D5B94` | `804D5BA0` |  |
| L9 | `804D5C40` | `804D5C4C` |  |
| L10 | `804D5CEC` | `804D5CF8` |  |


### AP level unlock safety rules

Recommended World Access behavior:
- Unlock several normal level states, e.g. L1-L5.
- Do not unlock only L11.
- Never overwrite `2` or `3` with `1`.
- Never write Green/Stump/Trophy addresses as AP received items.

Example:

```python
def unlock_level_state(addr):
    value = read_u8(addr)
    if value == 0:
        write_u8(addr, 1)
```

---

## 7. World / Block Layout Summary

### Normal worlds W1-W7

Confirmed:
- W1-W4 address pattern confirmed.
- W1/W2 predictions were confirmed.
- W4 addresses derived from W4L1 Trophy `804CF178` were confirmed.
- W5-W7 still need final confirmation unless later verified.

Normal world stride:

```text
World stride = 0x764 = 11 levels * 0xAC
```

L1 Trophy anchors:

| World | L1 Trophy | Status | Notes |
|---|---:|---|---|
| W1 | `804CDB4C` | confirmed | derived backwards from W3 |
| W2 | `804CE2B0` | confirmed | derived backwards from W3 |
| W3 | `804CEA14` | confirmed | original confirmed block |
| W4 | `804CF178` | confirmed | W4L1 Trophy anchor confirmed |
| W5 | `804CF8DC` | predicted | not yet fully confirmed |
| W6 | `804D0040` | predicted | not yet fully confirmed |
| W7 | `804D07A4` | predicted | no Level 11; no Stump Pieces |

### Easy and Hard L1 Trophy anchors

Easy:
- Easy W1L2 normal/non-Mirror Trophy observed at `804CA83C`.
- Easy W1L1 Trophy anchor inferred as `804CA790`.
- Easy W1-W7 predictions use the same `0x764` world stride and `0xAC` level stride.

| Difficulty | World | L1 Trophy | Status |
|---|---|---:|---|
| Easy | W1 | `804CA790` | inferred anchor from W1L2 |
| Easy | W2 | `804CAEF4` | predicted |
| Easy | W3 | `804CB658` | predicted |
| Easy | W4 | `804CBDBC` | predicted |
| Easy | W5 | `804CC520` | predicted |
| Easy | W6 | `804CCC84` | predicted |
| Easy | W7 | `804CD3E8` | predicted |
| Hard | W1 | `804D0F08` | confirmed |
| Hard | W2 | `804D166C` | predicted |
| Hard | W3 | `804D1DD0` | predicted |
| Hard | W4 | `804D2534` | predicted |
| Hard | W5 | `804D2C98` | predicted |
| Hard | W6 | `804D33FC` | predicted |
| Hard | W7 | `804D3B60` | predicted |

### Worlds A-C

Confirmed/likely A-C structure:
- A-C are not directly after W7 in the earlier normal-world prediction.
- A-C behave like bonus/Level 11-style levels.
- No Green Gems.
- No Stump Temple Pieces.
- State + Trophy only.
- Progress is shared between Easy and Normal.
- Level stride still `0xAC`.

A/B/C block anchors:

| Block | L1 Trophy | Status | Notes |
|---|---:|---|---|
| WA | `804D42C4` | confirmed | derived from A2/A3/A4 Trophy |
| WB | `804D497C` | confirmed | derived from B2 Trophy |
| W? | `804D5034` | unknown gap block | previous wrong C prediction; likely some other/unused block |
| WC | `804D56EC` | confirmed from C2 | C2 Trophy `804D5798` |

A-C stride pattern:
- A -> B: `0x6B8`
- B -> unknown gap block: `0x6B8`
- unknown gap block -> C: `0x6B8`

### W7 / Stump Temple

- W7 has no Level 11.
- W7 has no Stump Temple Pieces because it is the Stump Temple.
- W7 may still have Green Gems.
- Do not include W7 Stump checks.

### A-C AP check note

- A-C have no Level 11.
- A-C have no Green Gems.
- A-C have no Stump Temple Pieces.
- Track State + Trophy only for direct checks.
- Do not make difficulty-specific duplicate AP checks for A-C unless later testing disproves shared progress.

---

## 8. Junk, Vehicle Parts, Recipes, and Vehicle Fusions

### Address formula / inventory slots

Anchor:

```text
Normal Secret Energy current/live = 804DF4A2
Normal Secret Energy saved        = 9046F74E
```

For inventory slot index `i`, 1-based:

```text
current/live = 804DF4A2 + (i - 1)
saved        = 9046F74E + (i - 1)
```

Current interpretation:
- Slots 1–25 are the known normal junk items.
- Slot 25 is Part Base, which is always available / effectively infinite.
- Slots 26–30 are Vehicle Parts in the confirmed in-memory order:
  1. Can
  2. Periscope
  3. Screw
  4. Rocket Engine
  5. Wing

### Normal junk item inventory/count addresses

| # | Junk Item | Fundbereich laut Quelle | Offset from Secret Energy | Current/live | Saved | Notes |
|---:|---|---|---:|---:|---:|---|
| 1 | Secret Energy | Empty Lot 1–5 | `+0` | `804DF4A2` | `9046F74E` |  |
| 2 | Bent Nails | Empty Lot 6–8 | `+1` | `804DF4A3` | `9046F74F` |  |
| 3 | Prairie Wind | Empty Lot 9–10 | `+2` | `804DF4A4` | `9046F750` |  |
| 4 | Gear | Neighbor’s House 1–5 | `+3` | `804DF4A5` | `9046F751` |  |
| 5 | Rubber Bands | Neighbor’s House 6–8 | `+4` | `804DF4A6` | `9046F752` |  |
| 6 | Buttons | Neighbor’s House 9–10 | `+5` | `804DF4A7` | `9046F753` |  |
| 7 | Sun Sand | Sizzlin’ Desert 1–5 | `+6` | `804DF4A8` | `9046F754` |  |
| 8 | Flammable Mud | Sizzlin’ Desert 6–8 | `+7` | `804DF4A9` | `9046F755` |  |
| 9 | Cactus | Sizzlin’ Desert 9–10 | `+8` | `804DF4AA` | `9046F756` |  |
| 10 | Snowflake | Chill Mountain 1–5 | `+9` | `804DF4AB` | `9046F757` |  |
| 11 | Ice Droplet | Chill Mountain 6–8 | `+10` | `804DF4AC` | `9046F758` |  |
| 12 | Aurora Light | Chill Mountain 9–10 | `+11` | `804DF4AD` | `9046F759` |  |
| 13 | Gold Coin | Ocean Treasure 1–5 | `+12` | `804DF4AE` | `9046F75A` |  |
| 14 | Shell | Ocean Treasure 6–8 | `+13` | `804DF4AF` | `9046F75B` |  |
| 15 | Shark Tooth | Ocean Treasure 9–10 | `+14` | `804DF4B0` | `9046F75C` |  |
| 16 | New Dream Stuff | Space Station 1–5 | `+15` | `804DF4B1` | `9046F75D` |  |
| 17 | Mystery Tablet | Space Station 6–8 | `+16` | `804DF4B2` | `9046F75E` |  |
| 18 | Ether | Space Station 9–10 | `+17` | `804DF4B3` | `9046F75F` |  |
| 19 | Sugar | Candy Island 3 | `+18` | `804DF4B4` | `9046F760` |  |
| 20 | Cream | Candy Island 6 | `+19` | `804DF4B5` | `9046F761` |  |
| 21 | Darkness | Haunted House 3 | `+20` | `804DF4B6` | `9046F762` |  |
| 22 | Fear | Haunted House 6 | `+21` | `804DF4B7` | `9046F763` |  |
| 23 | Noise | City 3 | `+22` | `804DF4B8` | `9046F764` |  |
| 24 | Smoke | City 6 | `+23` | `804DF4B9` | `9046F765` |  |
| 25 | Part Base | Always Available | `+24` | `804DF4BA` | `9046F766` | Always available / effectively infinite; address may not behave like a normal finite consumable count |

### Vehicle Part inventory / obtained addresses

Vehicle Parts directly continue the same inventory slot pattern after Part Base.

Important:
- Correct in-memory order is **Can, Periscope, Screw, Rocket Engine, Wing**.
- This differs from a simple source-order list because Wing's source is Haunted House 5, but its inventory slot is after Rocket Engine.
- `804DF4BB` through `804DF4BF` stay at `1` after the parts are obtained.
- `9046F767` through `9046F76B` are cleared/consumed by the Junk Factory vehicle-building flow when all five Vehicle Parts have been collected.
- The game saves when those saved values are cleared, before Rocket Ship is actually built.
- Do not use `9046F767`–`9046F76B` as one-way AP check flags.

| Slot | Vehicle Part | Fundbereich laut Quelle | Offset from Secret Energy | Live/current / obtained | Saved / inventory | Status / Notes |
|---:|---|---|---:|---:|---:|---|
| 26 | Can | Candy Island 1 | `+25` | `804DF4BB` | `9046F767` | Live confirmed; stays `1` after obtained |
| 27 | Periscope | Haunted House 1 | `+26` | `804DF4BC` | `9046F768` | Order confirmed |
| 28 | Screw | City 1 | `+27` | `804DF4BD` | `9046F769` | Order confirmed |
| 29 | Rocket Engine | City 5 | `+28` | `804DF4BE` | `9046F76A` | Order confirmed |
| 30 | Wing | Haunted House 5 | `+29` | `804DF4BF` | `9046F76B` | Order confirmed |

### Vehicle Part consumption / Junk Factory behavior

Observed behavior:
- When entering Junk Factory with all five Vehicle Parts collected, the saved Vehicle Part values are set to `0`:

```text
9046F767 = Can saved/inventory
9046F768 = Periscope saved/inventory
9046F769 = Screw saved/inventory
9046F76A = Rocket Engine saved/inventory
9046F76B = Wing saved/inventory
```

- The game saves at that point.
- At that point, Rocket Ship has not necessarily been built yet.
- The live/current obtained flags remain `1`:

```text
804DF4BB = Can obtained
804DF4BC = Periscope obtained
804DF4BD = Screw obtained
804DF4BE = Rocket Engine obtained
804DF4BF = Wing obtained
```

Implication:
- The `804DF4BB`–`804DF4BF` values are better candidates for Vehicle Part obtained checks.
- The `9046F767`–`9046F76B` values are not safe as AP location checks because they can be consumed/cleared and saved.

### Recipe unlock flags and fusion/object output flags

Canonical order:
- Use address order as the standard order.
- This matches the in-game display order.
- Do not sort by unlock-source order.

Current interpretation as of 2026-08-03:
- Direct AP recipe unlocks use confirmed individual bytes in the `804DF4E0` area.
- This is **not** a complete linear `804DF4E0` through `804DF4FA` block.
- Only the confirmed rows below should currently be generated as AP recipe items.
- `804DF55C` through `804DF57E` are interpreted as recipe/object output availability flags, not recipe unlock flags.
- Do not use `804DF55C` through `804DF57E` as AP received recipe unlocks unless later testing proves a specific object flag is needed.

Confirmed direct recipe unlock bytes:

| Address | Recipe / Unlock |
|---:|---|
| `804DF4E0` | Moving Tile Set |
| `804DF4E1` | Sliding Tile |
| `804DF4E2` | Magnet Set |
| `804DF4E3` | Drawbridge |
| `804DF4E4` | Conveyor Belt |
| `804DF4E5` | Turntable |
| `804DF4E6` | Bumper Set |
| `804DF4E7` | Gear |
| `804DF4E8` | Moving Curve Set |
| `804DF4E9` | Cannon |
| `804DF4EA` | Thorn |
| `804DF4EB` | Scissors |
| `804DF4EE` | Magnifying Glass |
| `804DF4EF` | Spring |
| `804DF4F5` | Seesaw Set |
| `804DF4F9` | Press |
| `804DF4FA` | Punch |
| `804DF4FB` | Basic Parts Set: Neighbor's House |
| `804DF4FC` | Basic Parts Set: Sizzlin' Desert |

Currently unconfirmed / not unlocked by previously guessed direct bytes:
- Blinking Tile
- Moving Pipe Set
- Dash Tunnel Set
- Fan Set
- Size Changing Tunnel Set
- Upside Down Stage Device
- Toy Train
- Upside Down Ball
- Warp
- Melody Set
- Basic Parts Set: Chill Mountain
- Basic Parts Set: Ocean Treasure
- Basic Parts Set: Space Station
- Basic Parts Set: Candy Island
- Basic Parts Set: Haunted House
- Basic Parts Set: City

Object/output flag reference block:

| Address | Recipe/Object | Unlock source |
|---:|---|---|
| `804DF55C` | Moving Tile Set | The Empty Lot 11, any difficulty |
| `804DF55D` | Sliding Tile | The Empty Lot 11, any difficulty |
| `804DF55E` | Magnet Set | The Empty Lot 11, any difficulty |
| `804DF55F` | Drawbridge | Neighbor's House 03, any difficulty |
| `804DF560` | Conveyor Belt | Neighbor's House 06, any difficulty |
| `804DF561` | Turntable | Neighbor's House 09, any difficulty |
| `804DF562` | Bumper Set | Neighbor's House 11, any difficulty |
| `804DF563` | Gear | Neighbor's House 11, any difficulty |
| `804DF564` | Moving Curve Set | Neighbor's House 05, any difficulty |
| `804DF565` | Cannon | Sizzlin' Desert 04, any difficulty |
| `804DF566` | Thorn | Sizzlin' Desert 08, any difficulty |
| `804DF567` | Scissors | Sizzlin' Desert 11, any difficulty |
| `804DF568` | Blinking Tile | Chill Mountain 02, any difficulty |
| `804DF569` | Moving Pipe Set | Chill Mountain 11, any difficulty |
| `804DF56A` | Magnifying Glass | Chill Mountain 05, any difficulty |
| `804DF56B` | Spring | Ocean Treasure 02, any difficulty |
| `804DF56C` | Dash Tunnel Set | Ocean Treasure 03, any difficulty |
| `804DF56D` | Fan Set | Ocean Treasure 04, any difficulty |
| `804DF56E` | Size Changing Tunnel Set | Ocean Treasure 11, any difficulty |
| `804DF56F` | Upside Down Stage Device | Ocean Treasure 11, any difficulty |
| `804DF570` | Toy Train | Ocean Treasure 11, any difficulty |
| `804DF571` | Seesaw Set | Ocean Treasure 05, any difficulty |
| `804DF572` | Upside Down Ball | Haunted House 03 with Kororin Capsule |
| `804DF573` | Warp | Haunted House 01 |
| `804DF574` | Melody Set | City 06 |
| `804DF575` | Press | Haunted House 05 |
| `804DF576` | Punch | Something related to Haunted House |
| `804DF577` | Basic Parts Set: Neighbor's House | Neighbor's House 11, any difficulty |
| `804DF578` | Basic Parts Set: Sizzlin' Desert | Sizzlin' Desert 11, any difficulty |
| `804DF579` | Basic Parts Set: Chill Mountain | Chill Mountain 11, any difficulty |
| `804DF57A` | Basic Parts Set: Ocean Treasure | Ocean Treasure 11, any difficulty |
| `804DF57B` | Basic Parts Set: Space Station | Space Station 11, any difficulty |
| `804DF57C` | Basic Parts Set: Candy Island | All Candy Island stages or all Candy Island 2 stages |
| `804DF57D` | Basic Parts Set: Haunted House | All Haunted House stages |
| `804DF57E` | Basic Parts Set: City | All City stages |

### Vehicle fusion / built flags

The Vehicle built/unlock flags continue immediately after the recipe/object block:

| Address | Vehicle/Fusion | Meaning | Status / Notes |
|---:|---|---|---|
| `804DF57F` | Submarine | Submarine built/unlocked | Confirmed |
| `804DF580` | Rocket Ship | Rocket Ship built/unlocked | Confirmed |

#### Vehicle cutscene / manual bonus-level gates

These bytes control whether the vanilla Submarine/Rocket Ship part cutscenes have been watched enough for manual vehicle-part bonus level unlocks to appear.

| Difficulty | Address | Recommended AP test value | Meaning |
|---|---:|---:|---|
| Easy | `804DF903` | `15`, `31`, `79`, or `95` | Manual vehicle-part bonus unlock gate for Easy |
| Normal | `804DF908` | `15`, `31`, `79`, or `95` | Manual vehicle-part bonus unlock gate for Normal |

Hard does not need Submarine / Rocket Ship building for these cutscenes, so no Hard address is currently needed.

Observed values:
- `15`: no AP-authorized vehicle cutscene gate.
- `31`: allows manual unlocks for Candy Island L1, Haunted House L1, and City L1; suppresses the "you need these parts for the Submarine" cutscene state.
- `79`: allows manual unlocks for Haunted House L5 and City L5.
- `95`: allows all five vehicle-part bonus levels to be manually unlocked; effectively both cutscenes watched.

AP implication:
- Do not keep Easy `804DF903` and Normal `804DF908` forced to `95` globally.
- Set `31` only when AP has authorized the W5/Submarine-side progression for that difficulty.
- Set `79` only when AP has authorized the W6/Rocket-side progression for that difficulty.
- Set `95` only when both sides are AP-authorized for that difficulty.
- Keep dangerous L11 state values at `0` on the world map when they are not explicitly needed for a safe Anthony's House / Junk Factory context, because L11 `State=3` can trigger vanilla events and world unlock side effects.

#### Submarine behavior

`804DF57F = 1`:
- Allows entering World 5 / Ocean Treasure once the vanilla requirement event has been triggered by W4L11 State = `3`.
- Manually setting this flag removes/passes the Submarine requirement.
- Manually setting this flag does **not** auto-unlock W5 levels.
- Building the Submarine normally in Junk Factory also auto-unlocks W5 L1-L5.

AP implication:
- If AP gives Submarine by writing `804DF57F = 1`, the client should separately unlock safe W5 level states if the AP item is intended to grant access.

Recommended AP receive behavior:

```python
def receive_submarine():
    write_u8(0x804DF57F, 1)

    for addr in [
        0x804CF8D0,  # W5 L1 State
        0x804CF97C,  # W5 L2 State
        0x804CFA28,  # W5 L3 State
        0x804CFAD4,  # W5 L4 State
        0x804CFB80,  # W5 L5 State
    ]:
        if read_u8(addr) == 0:
            write_u8(addr, 1)
```

#### Rocket Ship behavior

`804DF580 = 1`:
- Same broad behavior as Submarine, but one world later.
- Allows passing the Rocket Ship requirement.
- Manually setting this flag removes/passes the Rocket Ship requirement.
- Manually setting this flag does **not** auto-unlock the relevant next world levels.
- Building the Rocket Ship normally in Junk Factory auto-unlocks the relevant next world L1-L5.

Likely AP receive behavior:

```python
def receive_rocket_ship():
    write_u8(0x804DF580, 1)

    for addr in [
        0x804D0034,  # W6 L1 State
        0x804D00E0,  # W6 L2 State
        0x804D018C,  # W6 L3 State
        0x804D0238,  # W6 L4 State
        0x804D02E4,  # W6 L5 State
    ]:
        if read_u8(addr) == 0:
            write_u8(addr, 1)
```

Note:
- The W6 level-state addresses are still based on the predicted W6 table unless separately confirmed.
- Keep Vehicle requirement flags and World Access / level-state unlocks conceptually separate in the AP design.

### Drawbridge-specific fusion flag search

Drawbridge vs Gear fusion comparison:
- A broad fusion scan produced 231 addresses changing to `1` for Drawbridge.
- Gear fusion caused 229 of those same addresses to also become `1`.
- Two addresses stayed `0` for Gear and became `1` for Drawbridge:

| Address | Candidate meaning |
|---:|---|
| `804DF3EF` | Drawbridge-specific candidate; needs persistence/write testing |
| `804DF55F` | Drawbridge recipe/object flag; canonical recipe block |

Likely conclusion:
- `804DF55F` is the standard recipe/object availability flag for Drawbridge.
- `804DF3EF` may be another Drawbridge-specific flag/copy/UI/build-state value and needs more testing.


### AP-sent useful junk items

If the YAML option enables junk items, AP may send normal junk as useful items. These should increase the junk count/inventory and should be useful for Junk Factory fusions.

Suggested option shapes:

```yaml
junk_items: true
junk_item_bundle_size: 1
```

or:

```yaml
junk_items: useful   # off / filler / useful
junk_item_bundle_size: 1
```

Recommended AP item names:
- `Junk: Secret Energy`
- `Junk: Bent Nails`
- ...
- `Junk: Smoke`

Do not include Part Base as a normal finite junk item by default because it behaves like an always-available/special ingredient.
Vehicle Parts should remain separate AP items/checks, not normal junk.

Client-side receive example:

```python
JUNK_ITEMS = {
    "Secret Energy": 0x804DF4A2,
    "Bent Nails": 0x804DF4A3,
    "Prairie Wind": 0x804DF4A4,
    "Gear": 0x804DF4A5,
    "Rubber Bands": 0x804DF4A6,
    "Buttons": 0x804DF4A7,
    "Sun Sand": 0x804DF4A8,
    "Flammable Mud": 0x804DF4A9,
    "Cactus": 0x804DF4AA,
    "Snowflake": 0x804DF4AB,
    "Ice Droplet": 0x804DF4AC,
    "Aurora Light": 0x804DF4AD,
    "Gold Coin": 0x804DF4AE,
    "Shell": 0x804DF4AF,
    "Shark Tooth": 0x804DF4B0,
    "New Dream Stuff": 0x804DF4B1,
    "Mystery Tablet": 0x804DF4B2,
    "Ether": 0x804DF4B3,
    "Sugar": 0x804DF4B4,
    "Cream": 0x804DF4B5,
    "Darkness": 0x804DF4B6,
    "Fear": 0x804DF4B7,
    "Noise": 0x804DF4B8,
    "Smoke": 0x804DF4B9,
}

ap_caused_junk_deltas = {}


def receive_junk_item(name, amount=1):
    live_addr = JUNK_ITEMS[name]
    saved_addr = 0x9046F74E + (live_addr - 0x804DF4A2)
    before = read_u8(live_addr)
    saved_before = read_u8(saved_addr)
    after = min(before + amount, 255)
    saved_after = min(saved_before + amount, 255)
    write_u8(live_addr, after)
    write_u8(saved_addr, saved_after)

    actual_delta = max(0, after - before)
    if actual_delta:
        ap_caused_junk_deltas[live_addr] = ap_caused_junk_deltas.get(live_addr, 0) + actual_delta
```

### Indirect junk reward location detection

Some checks do not have persistent collectible flags:
- Hard-mode Stump-style pickups only grant junk.
- A-C Stump-style/junk reward locations have no direct Green/Stump RAM flag.

With the exact current-level snapshot, these can be detected by observing matching junk count increases while in the expected level.

Safety rules:
- Snapshot all junk counts on level entry.
- Only evaluate indirect junk checks for the exact `(difficulty, world_index, level_index)` mapping.
- Ignore AP-caused junk writes by subtracting `ap_caused_junk_deltas`.
- Send each indirect location only once.
- Do not use `junk_count > 0` as a one-way location flag.

Example for Hard W1L1:

```python
# difficulty 2 = Hard, world 0 = W1, level 0 = L1
INDIRECT_JUNK_CHECKS = {
    (2, 0, 0): {
        "location": "Hard W1L1 Stump Temple Piece",
        "junk_addr": 0x804DF4A2,  # Secret Energy
        "amount": 1,
    },
}


def get_real_junk_delta(addr, before, now):
    raw_delta = max(0, now - before)
    ignored = min(raw_delta, ap_caused_junk_deltas.get(addr, 0))
    ap_caused_junk_deltas[addr] = ap_caused_junk_deltas.get(addr, 0) - ignored
    return raw_delta - ignored
```

### AP safety notes for junk/fusion/vehicles

#### Normal junk counts

- Do not use normal junk count addresses as simple one-way AP checks because counts can decrease when spent.
- They may be useful if AP sends actual junk items, but saved/current behavior must be handled carefully.
- Part Base should probably not be sent as a normal finite consumable unless later testing shows a meaningful value.

#### Vehicle Parts

- Vehicle Parts are now confirmed to directly follow the normal junk inventory block after Part Base.
- `804DF4BB`–`804DF4BF` are good candidates for Vehicle Part obtained checks because they stay `1` after obtaining the parts.
- `9046F767`–`9046F76B` are unsafe as AP checks because Junk Factory clears them and saves before the Rocket Ship is necessarily built.
- If AP sends Vehicle Parts as items and still wants to allow vanilla vehicle-building behavior, the client may need to write both:
  - the live/current obtained flag
  - the saved/inventory value
- This needs careful edge-case handling because the vanilla vehicle flow can consume/clear saved part values.

#### Vehicle built flags

- `804DF57F` and `804DF580` are strong AP item write targets for direct Submarine / Rocket Ship unlocks.
- Manual Vehicle flag writes do not perform the vanilla L1-L5 level-state unlock batch.
- Therefore AP World Access / Vehicle Access should still write safe level-state unlocks separately.

#### Recipe flags

- AP received recipe items should write the dedicated recipe unlock block.
- Address formula: Moving Tile Set starts at `804DF4E0`; each next canonical recipe is `+1`.
- Example: receiving Drawbridge should write `804DF4E3 = 1`.
- Example confirmed by testing notes: Cannon is `804DF4E9`, Thorn is `804DF4EA`.
- If recipes are also AP locations, avoid self-triggering by clearly separating:
  - received-item writes
  - check detection
- Further testing should confirm whether direct recipe unlock flags persist after save/reload.

### Current unknowns / useful next tests

- Confirm save/reload persistence of `804DF4BB`–`804DF4BF` after obtaining Vehicle Parts.
- Confirm whether writing only the live/current Vehicle Part flags is enough for the Junk Factory to recognize parts.
- Confirm whether writing only the saved Vehicle Part values is enough for the Junk Factory to recognize parts.
- Test the exact edge case where saved Vehicle Part values are cleared, game saves, but Rocket Ship has not yet been built.
- Confirm W6 L1-L5 state addresses in practice if Rocket Ship AP receive behavior unlocks W6.
- Continue testing recipe flag write behavior and persistence.

### Updated critical vehicle AP rule

Observed after the earlier notes:
- If Submarine or Rocket Ship is manually granted without also unlocking safe target-world levels, the game can enter the next world with no levels unlocked and crash.
- The cutscene/world-entry availability check is based on whether the vehicle built flag is `1`:
  - `804DF57F = 1` for Submarine/W5
  - `804DF580 = 1` for Rocket Ship/W6
- Manually setting the vehicle flag does not perform the vanilla L1-L5 unlock batch.

Therefore:

```text
Never write 804DF57F or 804DF580 alone.
Always unlock the target world's safe starting level states first or at the same time.
```

Safer AP receive order:

```python
def unlock_levels(addrs):
    for addr in addrs:
        if read_u8(addr) == 0:
            write_u8(addr, 1)


def receive_submarine():
    unlock_levels([
        0x804CF8D0,  # W5 L1 State
        0x804CF97C,  # W5 L2 State
        0x804CFA28,  # W5 L3 State
        0x804CFAD4,  # W5 L4 State
        0x804CFB80,  # W5 L5 State
    ])
    write_u8(0x804DF57F, 1)


def receive_rocket_ship():
    unlock_levels([
        0x804D0034,  # W6 L1 State
        0x804D00E0,  # W6 L2 State
        0x804D018C,  # W6 L3 State
        0x804D0238,  # W6 L4 State
        0x804D02E4,  # W6 L5 State
    ])
    write_u8(0x804DF580, 1)
```


### Vehicle/world access split YAML option

Default AP design should be safe and simple:

```text
Submarine implies safe W5 / Ocean Treasure enterability.
Rocket Ship implies safe W6 / Space Station enterability.
```

In this default mode, receiving Submarine or Rocket Ship should also unlock the safe starting levels for the target world so the visible vehicle cannot create a crashy empty-world entry.

Desired future YAML option:

```yaml
separate_vehicle_requirements: true
```

or:

```yaml
split_vehicle_world_access: true
```

Meaning in split mode:

```text
W5 requires both:
- Submarine item
- W5 / Ocean Treasure Access item

W6 requires both:
- Rocket Ship item
- W6 / Space Station Access item
```

Important distinction:

```text
AP logical vehicle possession != physical in-game vehicle RAM flag
```

In split mode, the client may remember that AP gave the Submarine/Rocket Ship, but the physical RAM flags should be context-gated so vanilla cannot allow unsafe entry.

Known vehicle flags:

| Address | Vehicle | Risk |
|---:|---|---|
| `804DF57F` | Submarine | If `1`, game can allow W5 entry even without W5 levels unlocked, causing crash risk. |
| `804DF580` | Rocket Ship | If `1`, game can allow W6 entry even without W6 levels unlocked, causing crash risk. |

World-map/menu gating rule:

```text
Submarine RAM flag may be 1 only if AP has Submarine AND W5 Access.
Rocket Ship RAM flag may be 1 only if AP has Rocket Ship AND W6 Access.
Otherwise force the physical flag to 0 when it is safe to do so outside active gameplay.
```

The old yellow-crystal value must not be used for this. Until a real world-map/menu screen-state is found, vehicle flag cleanup should be conservative and should not run while `in_level == True`.

Pseudo-code:

```python
SUBMARINE_FLAG = 0x804DF57F
ROCKET_SHIP_FLAG = 0x804DF580


def enforce_vehicle_flags_split_mode(in_level):
    if in_level:
        return

    submarine_allowed = has_ap_item("Submarine") and has_ap_item("W5 Access")
    rocket_allowed = has_ap_item("Rocket Ship") and has_ap_item("W6 Access")

    # Conservative physical RAM gating.
    write_u8(SUBMARINE_FLAG, 1 if submarine_allowed else 0)
    write_u8(ROCKET_SHIP_FLAG, 1 if rocket_allowed else 0)
```

Open task:
- Find a real world-map / difficulty-select / menu state if more precise vehicle UI gating is needed.
- Decide whether W5/W6 Access in split mode should unlock L1-L5 only when both the vehicle and world access are present, or whether W5/W6 Access may pre-unlock levels while the vehicle flag remains hidden until the vehicle item arrives.



---

## 9. Marble Unlock Flags

Marble unlock flags found:

```text
804DF36E - 804DF381 = Marble unlock flags
```

Total slots:

```text
0x804DF381 - 0x804DF36E + 1 = 0x14 = 20 marbles
```

State logic:

| Value | Meaning |
|---:|---|
| `0` | locked |
| `1` | unlocked with “New” label |
| `2` | unlocked/seen, “New” label cleared |

Correction:
- `2` does not mean “always unlocked”.
- The first three marbles start at `2` because they are vanilla start marbles and already seen.

### Marble address/order table

The address order should be treated as canonical for AP/RAM. It matches the Speedrun.com-style ball list from Marble through Figure Roller.

| # | Address | Marble | Vanilla unlock source / notes |
|---:|---:|---|---|
| 1 | `804DF36E` | Marble | Standard / vanilla start marble |
| 2 | `804DF36F` | Ladybug | Standard / vanilla start marble |
| 3 | `804DF370` | Cat | Standard / vanilla start marble |
| 4 | `804DF371` | Dog | 10 Gold Trophies on Easy per Speedrun guide; older GameFAQs-style sources may disagree and should be RAM-verified |
| 5 | `804DF372` | Pig | 3 Gold Trophies on Normal |
| 6 | `804DF373` | Penguin | 5 Gold Trophies on Normal |
| 7 | `804DF374` | Frog | 8 Gold Trophies on Normal |
| 8 | `804DF375` | Rugby Ball / Football | 20 Gold Trophies on Easy |
| 9 | `804DF376` | Fishbowl / Goldfish Bowl | 12 Gold Trophies on Normal |
| 10 | `804DF377` | Anglerfish | Ocean Treasure 11 on Normal |
| 11 | `804DF378` | Chick-N-Egg / Egg | 16 Gold Trophies on Normal |
| 12 | `804DF379` | Baseball | 30 Gold Trophies on Easy |
| 13 | `804DF37A` | Bomb | 20 Gold Trophies on Normal |
| 14 | `804DF37B` | Earth | Space Station 11 on Normal |
| 15 | `804DF37C` | UFO | 25 Gold Trophies on Normal |
| 16 | `804DF37D` | Saturn | 30 Gold Trophies on Normal |
| 17 | `804DF37E` | Broken TV | 35 Gold Trophies on Normal |
| 18 | `804DF37F` | Hedgehog | 40 Gold Trophies on Normal |
| 19 | `804DF380` | Panda | In one attempt, die 3 times and then reach the goal; reset with A/1 does not count as death. Older sources may disagree; RAM-verify. |
| 20 | `804DF381` | Figure Roller | Secret code or Stump Temple 10 on Normal |

Notes from the unlock guide:
- Level-based unlocks do not trigger from Free Play; they require play from the World Map.
- Level-based unlocks without a concrete difficulty listed may be separated per difficulty by vanilla.
- For marbles with explicit Easy/Normal requirements, AP logic should respect those difficulties when checking vanilla behavior.

### AP usage

AP should treat marbles as AP-owned unlock flags.

Rules:
- Received marble item: write `1` if currently `0`.
- Do not lower `2` back to `1`.
- If marble randomization is enabled, suppress vanilla marble unlocks caused by Easy/Normal trophy counts or level clears by forcing disallowed marble flags back to `0`.
- For AP start randomization, set all marbles to `0` and then give exactly one starting marble.
- Starting marble is treated as AP-owned from the beginning. It may be written as `1` when first initialized, and if the game later changes it to `2` after use, do not force it back to `1`.
- Newly received AP marbles should probably be written as `1` so the player sees the “New” label.

Example:

```python
MARBLES = [
    ("Marble", 0x804DF36E),
    ("Ladybug", 0x804DF36F),
    ("Cat", 0x804DF370),
    ("Dog", 0x804DF371),
    ("Pig", 0x804DF372),
    ("Penguin", 0x804DF373),
    ("Frog", 0x804DF374),
    ("Rugby Ball / Football", 0x804DF375),
    ("Fishbowl / Goldfish Bowl", 0x804DF376),
    ("Anglerfish", 0x804DF377),
    ("Chick-N-Egg / Egg", 0x804DF378),
    ("Baseball", 0x804DF379),
    ("Bomb", 0x804DF37A),
    ("Earth", 0x804DF37B),
    ("UFO", 0x804DF37C),
    ("Saturn", 0x804DF37D),
    ("Broken TV", 0x804DF37E),
    ("Hedgehog", 0x804DF37F),
    ("Panda", 0x804DF380),
    ("Figure Roller", 0x804DF381),
]


def init_ap_starting_marble(start_name):
    for name, addr in MARBLES:
        write_u8(addr, 0)

    for name, addr in MARBLES:
        if name == start_name:
            # AP-owned from start; leave later value 2 alone after it has been used.
            write_u8(addr, 1)
            break


def enforce_marbles():
    for name, addr in MARBLES:
        allowed = has_ap_item(f"Marble: {name}") or is_starting_marble(name)

        if allowed:
            if read_u8(addr) == 0:
                write_u8(addr, 1)
        else:
            if read_u8(addr) != 0:
                write_u8(addr, 0)
```

### Repeated vanilla marble unlock popup guard

Observed:
- Vanilla marble unlock popups repeat after every level completion if the vanilla requirement is already satisfied and AP manually resets the marble flag to `0`.
- Example: Pig unlocks from 3 Normal Gold trophies. If AP sets Pig back to `0`, completing any later level can trigger the Pig unlock popup again.
- This suggests vanilla post-level reward logic checks something like `if requirement_met and marble_flag == 0: unlock + queue popup`.

Workaround:
- During active levels / result transitions, temporarily set AP-locked but vanilla-unlockable marbles to `2` so vanilla thinks they are already unlocked/seen and does not queue popups.
- Outside active levels, restore AP-owned truth by locking marbles the player has not received.

```python
def fake_unlock_blocked_vanilla_marbles():
    for name, addr in MARBLES:
        allowed = has_ap_item(f"Marble: {name}") or is_starting_marble(name)
        if not allowed and read_u8(addr) == 0:
            # Use 2, not 1, to avoid New labels for fake unlocks.
            write_u8(addr, 2)


def enforce_ap_marble_locks():
    for name, addr in MARBLES:
        allowed = has_ap_item(f"Marble: {name}") or is_starting_marble(name)

        if allowed:
            if read_u8(addr) == 0:
                write_u8(addr, 1)
        else:
            if read_u8(addr) != 0:
                write_u8(addr, 0)


def enforce_marbles_with_popup_guard(in_level):
    if in_level:
        fake_unlock_blocked_vanilla_marbles()
    else:
        enforce_ap_marble_locks()
```

Caveat:
- If the game saves while fake-unlocked marbles are set to `2`, the save can contain temporary physical unlocks.
- AP should enforce its inventory truth on client startup and whenever safely outside active gameplay.

Important open task:
- Find selected/equipped marble address.
- This is important if AP locks the vanilla starting marbles and starts the player with a random marble.
- If the game has an equipped marble that becomes locked by AP enforcement, the client should switch it to an allowed marble before/when locking.

---
## 10. Figure Roller Head Unlock Flags

Figure Roller Head unlock flags found:

```text
804DF521 - 804DF52A = Figure Roller Head unlock flags
```

Total slots:

```text
0x804DF52A - 0x804DF521 + 1 = 0x0A = 10 heads
```

State logic is the same as marble unlocks:

| Value | Meaning |
|---:|---|
| `0` | locked |
| `1` | unlocked with “New” label |
| `2` | unlocked/seen, “New” label cleared |

### Figure Roller Head address/order table

Current expected address order:

| # | Address | Head | Vanilla unlock source / notes |
|---:|---:|---|---|
| 1 | `804DF521` | Charlie | Cheat code `robot, car, sunflower, bike, helicopter, strawberry`; or Stump Temple 10 on Normal; also unlocked automatically when Figure Roller is unlocked |
| 2 | `804DF522` | Snowman | 5 Gold Trophies on Hard |
| 3 | `804DF523` | Pumpkin | 10 Gold Trophies on Hard |
| 4 | `804DF524` | Paper Bag | 15 Gold Trophies on Hard |
| 5 | `804DF525` | Space Suit | 20 Gold Trophies on Hard |
| 6 | `804DF526` | Space Alien | 25 Gold Trophies on Hard |
| 7 | `804DF527` | Monster | 30 Gold Trophies on Hard |
| 8 | `804DF528` | Moai | 35 Gold Trophies on Hard |
| 9 | `804DF529` | Bomberman | 40 Platinums on Hard |
| 10 | `804DF52A` | Master Higgins | Cheat code `robot, car, sunflower, bike, helicopter, strawberry` |

Important behavior:
- Unlocking the Figure Roller marble automatically unlocks Charlie.
- If Figure Roller heads are AP-owned, vanilla Hard-mode Gold/Platinum unlocks and cheat-code unlocks should be suppressed unless AP has granted the corresponding head.
- Charlie is special because it may be allowed either by a dedicated Charlie item or by receiving the Figure Roller marble.

AP usage:

```python
FIGURE_HEADS = [
    ("Charlie", 0x804DF521),
    ("Snowman", 0x804DF522),
    ("Pumpkin", 0x804DF523),
    ("Paper Bag", 0x804DF524),
    ("Space Suit", 0x804DF525),
    ("Space Alien", 0x804DF526),
    ("Monster", 0x804DF527),
    ("Moai", 0x804DF528),
    ("Bomberman", 0x804DF529),
    ("Master Higgins", 0x804DF52A),
]

MARBLE_FIGURE_ROLLER = 0x804DF381
HEAD_CHARLIE = 0x804DF521


def receive_figure_roller():
    if read_u8(MARBLE_FIGURE_ROLLER) == 0:
        write_u8(MARBLE_FIGURE_ROLLER, 1)

    # Vanilla behavior: Figure Roller unlocks Charlie.
    if read_u8(HEAD_CHARLIE) == 0:
        write_u8(HEAD_CHARLIE, 1)


def enforce_figure_heads():
    for name, addr in FIGURE_HEADS:
        if name == "Charlie":
            allowed = has_ap_item("Marble: Figure Roller") or has_ap_item("Figure Roller Head: Charlie")
        else:
            allowed = has_ap_item(f"Figure Roller Head: {name}")

        if allowed:
            if read_u8(addr) == 0:
                write_u8(addr, 1)
        else:
            if read_u8(addr) != 0:
                write_u8(addr, 0)
```

Design choice to consider:
- Charlie may not need to be a separate AP item if Figure Roller always grants it.
- If Charlie is kept as a separate item, then Figure Roller should still imply Charlie as a free dependency/unlock.

Open tasks:
- Confirm the exact head order in RAM with direct tests if possible.
- Test persistence and menu behavior after direct writes and after vanilla unlocks.
- Find equipped/selected Figure Roller head address if needed for enforcement.

---
## 11. Worlds A-C Vanilla Unlocks, AP Suppression, and Indirect Stump/Junk Reward Locations

Worlds A-C have no direct Green Gem or Stump Temple Piece addresses.
They only appear to have State + Trophy tracking in the currently documented A-C blocks.

A-C:
- shared between Easy and Normal according to current RAM observations
- no Green Gems
- no Stump Pieces
- State + Trophy only

Important AP rule:
- Vanilla can unlock A-C levels from Green Crystal counts, certain L11 clears, and Hard-mode Ant counts.
- In AP, these vanilla unlocks should be treated as side effects and suppressed unless AP has granted the matching level/world access.
- Do not change the Green Crystal, Trophy, or Ant totals just to prevent vanilla unlocks.
- Instead, enforce the A-C level State flags based on AP inventory/logic.

### Vanilla A-C unlock requirements

Notes from the unlock guide:
- Level-based unlocks do not trigger from Free Play; they require play from the World Map.
- Level-based unlocks without a concrete difficulty listed may be separated per difficulty by vanilla.
- AP should not rely on these vanilla unlocks for progression unless explicitly designing a vanilla-like option.

### World A — Candy Island

| Level | Vanilla unlock |
|---|---|
| Candy Island 01 | Chill Mountain 11, any difficulty |
| Candy Island 02 | 20 Green Crystals |
| Candy Island 03 | The Empty Lot 11, any difficulty |
| Candy Island 04 | 26 Green Crystals |
| Candy Island 05 | 32 Green Crystals |
| Candy Island 06 | Sizzlin’ Desert 11, any difficulty |
| Candy Island 07 | 34 Green Crystals |
| Candy Island 08 | 43 Green Crystals |
| Candy Island 09 | 52 Green Crystals |
| Candy Island 10 | 62 Green Crystals |

### World A Hard/Ant variant — Candy Island 2

| Level | Vanilla unlock |
|---|---|
| Candy Island 2 01 | 3 Ants |
| Candy Island 2 02 | 6 Ants |
| Candy Island 2 03 | 21 Ants |
| Candy Island 2 04 | 24 Ants |
| Candy Island 2 05 | 39 Ants |
| Candy Island 2 06 | 42 Ants |
| Candy Island 2 07 | 57 Ants |
| Candy Island 2 08 | 60 Ants |
| Candy Island 2 09 | 75 Ants |
| Candy Island 2 10 | 78 Ants |

### World B — Haunted House

| Level | Vanilla unlock |
|---|---|
| Haunted House 01 | Chill Mountain 11, any difficulty |
| Haunted House 02 | 22 Green Crystals |
| Haunted House 03 | All of Haunted House 05 & City 05 |
| Haunted House 04 | 28 Green Crystals |
| Haunted House 05 | Ocean Treasure 11, any difficulty |
| Haunted House 06 | Space Station 11, any difficulty |
| Haunted House 07 | 37 Green Crystals |
| Haunted House 08 | 46 Green Crystals |
| Haunted House 09 | 55 Green Crystals |
| Haunted House 10 | 66 Green Crystals |

### World B Hard/Ant variant — Haunted House Darkness

| Level | Vanilla unlock |
|---|---|
| Haunted House Darkness 01 | 9 Ants |
| Haunted House Darkness 02 | 12 Ants |
| Haunted House Darkness 03 | 27 Ants |
| Haunted House Darkness 04 | 30 Ants |
| Haunted House Darkness 05 | 45 Ants |
| Haunted House Darkness 06 | 48 Ants |
| Haunted House Darkness 07 | 63 Ants |
| Haunted House Darkness 08 | 66 Ants |
| Haunted House Darkness 09 | 81 Ants |
| Haunted House Darkness 10 | 84 Ants |

### World C — City

| Level | Vanilla unlock |
|---|---|
| City 01 | Chill Mountain 11, any difficulty |
| City 02 | 24 Green Crystals |
| City 03 | Neighbor’s House 11, any difficulty |
| City 04 | 30 Green Crystals |
| City 05 | Ocean Treasure 11, any difficulty |
| City 06 | Space Station 11, any difficulty |
| City 07 | 40 Green Crystals |
| City 08 | 49 Green Crystals |
| City 09 | 58 Green Crystals |
| City 10 | 70 Green Crystals |

### World C Hard/Ant variant — Night City

| Level | Vanilla unlock |
|---|---|
| Night City 01 | 15 Ants |
| Night City 02 | 18 Ants |
| Night City 03 | 33 Ants |
| Night City 04 | 36 Ants |
| Night City 05 | 51 Ants |
| Night City 06 | 54 Ants |
| Night City 07 | 69 Ants |
| Night City 08 | 72 Ants |
| Night City 09 | 87 Ants |
| Night City 10 | 90 Ants |

### AP suppression for A-C unlocks

Possible enforcement approach:

```python
def enforce_bonus_level_access(level_addr, allowed):
    value = read_u8(level_addr)

    if allowed:
        if value == 0:
            write_u8(level_addr, 1)
    else:
        # Remove fresh vanilla unlocks.
        # Do not lower played/completed states unless a stricter AP mode requires it.
        if value == 1:
            write_u8(level_addr, 0)
```

Open task:
- Confirm whether Hard/Ant variants use the same A-C State/Trophy address blocks or separate blocks.
- Confirm whether A-C progress sharing applies to all relevant difficulties or only Easy/Normal.
- Determine whether AP will use per-level A-C access items, per-world A-C access items, or vanilla-like requirements as a YAML option.

### A-C indirect Stump/Junk reward locations

Certain A-C “Stump Temple Piece” style rewards can be represented as AP locations by watching the junk item reward gained from the level.

Candidate indirect A-C Stump/Junk reward locations:

```text
WA1
WA3
WA6

WB1
WB3
WB5
WB6

WC1
WC3
WC5
WC6
```

Important caveat:
- If AP sends junk items as received items, those writes can falsely look like junk reward increases.
- The client must suppress AP-caused junk count increases from location detection.

Possible suppression approach:

```python
ignore_next_junk_increase[junk_addr] += amount_written_by_ap
```

Safer approach:
- Only allow these indirect checks to trigger when the client knows the player just completed the matching A/B/C level.
- Avoid global “junk count increased = location” logic.

---
## 12. AP Logic Counters, Goals, and YAML Options

### AP-side progression counters only

Desired AP design includes progression counters that exist only in AP logic and should **not** write in-game collectible flags.

AP-side count items:
- `Green Gem`
- `Stump Temple Piece`

These are different from in-game collectible/check flags:

```text
In-game Green Gem flag collected -> client sends a location check to AP.
AP sends Green Gem item -> AP inventory count increases only; do not write Green Gem RAM.

In-game Stump flag/junk reward collected -> client sends a location check to AP.
AP sends Stump Temple Piece item -> AP inventory count increases only; do not write Stump RAM.
```

This prevents false checks, disappearing collectibles, and broken vanilla totals.

### W7 / Stump Temple access

The preferred design is to require an AP-side count of `Stump Temple Piece` items for W7 / Stump Temple access.

```python
def can_access_w7(state):
    return state.count("Stump Temple Piece") >= state.options.required_stump_pieces_for_w7
```

Possible YAML:

```yaml
required_stump_pieces_for_w7: 30
```

If a separate `W7 Access` item is kept as an option, logic can allow either:

```python
def can_access_w7(state):
    return (
        state.has("W7 Access")
        or state.count("Stump Temple Piece") >= state.options.required_stump_pieces_for_w7
    )
```

### Hard Mode access options

If the goal is Hard difficulty, Hard Mode can be unlocked in multiple AP designs.

Suggested YAML:

```yaml
goal: normal_w7_l10       # normal_w7_l10 / hard_w7_l10
hard_mode_unlock: item    # start / item / green_gems / vanilla
required_green_gems_for_hard: 40
required_stump_pieces_for_w7: 30
```

Logic:

```python
def can_access_hard_mode(state):
    option = state.options.hard_mode_unlock

    if option == "start":
        return True
    if option == "item":
        return state.has("Hard Mode")
    if option == "green_gems":
        return state.count("Green Gem") >= state.options.required_green_gems_for_hard
    if option == "vanilla":
        # Model vanilla or leave always true depending on implementation choice.
        return True

    return False
```

Goal examples:

```text
Normal goal:
    Stump Temple Pieces -> W7 -> Normal W7L10 -> goal

Hard goal, green-gem unlock:
    Green Gems -> Hard Mode
    Stump Temple Pieces -> W7
    Hard Mode + W7 -> Hard W7L10 -> goal

Hard goal, item unlock:
    Hard Mode item -> Hard Mode
    Stump Temple Pieces -> W7
    Hard Mode + W7 -> Hard W7L10 -> goal
```

### Wii Balance Board level checks

Optional AP check category:
- `Wii Balance Board Level 1` through `Wii Balance Board Level 100`.

Identification:

```text
8049D945 == 14       -> Wii Balance Board mode / level select / in-level
8049D94D == 0-99     -> Balance Board level index
```

Completion/check detection without physical Wii Balance Board:
- Use the transient goal-reached detector.
- Latch `goal_reached_this_attempt` while inside the level.
- Send the check on level exit or another safe post-goal transition.

Do not use difficulty for BB classification:
- `8049D95D` / `804E0DF8` can read `1` / Normal during Wii Balance Board stages.

YAML idea:

```yaml
wii_balance_board_levels: false   # false / true
```

If enabled, these checks should not require a physical Wii Balance Board unless a future option intentionally requires vanilla BB completion flags.

### Item classifications

Suggested classifications:

| Item type | Classification | Notes |
|---|---|---|
| World/level access | progression | Unlocks playable content. |
| `Hard Mode` | progression | If hard mode is gated by item. |
| `Green Gem` AP-side count item | progression | If used to unlock Hard Mode. |
| `Stump Temple Piece` AP-side count item | progression | If used to unlock W7. |
| Vehicles / vehicle access | progression | Especially Submarine/Rocket Ship. |
| Recipes | progression or useful | Progression if required by logic; useful otherwise. |
| Junk items | useful | Only if Junk Factory/fusions are enabled. |
| Marbles / Figure Roller heads | useful/cosmetic depending option | Marble randomization can make them practically useful. |
| Mirror / Reverse Controls traps | trap | Experimental until Mirror flag/result behavior is safer. |
| `Blackout Trap` | trap | Visual trap using `80490A42 = 3`; default duration should be short, around 10 seconds. |
| `Noclip Trap` | trap | Collision trap using `80CBD6EB = 0`; restore to `1` outside safe gameplay. |

---

## 13. AP Safety Rules Summary

Current highest-priority corrections from late 2026-07-06 testing:
- Do not use the old yellow-crystal/context value for screen-state gating.
- Use the combined in-level detector plus difficulty/world/level/stage snapshot for exact current-stage identity.
- Use `8049D945 == 14` plus `8049D94D` to identify Wii Balance Board levels; difficulty stays `1` there and is not enough.
- Use `8049D99F` as a save-slot safety/menu heuristic for Slot 3 writes.
- Use the transient goal-reached candidate group for Wii Balance Board checks because vanilla BB completion flags require the physical board.
- Do not write AP-side `Green Gem` or `Stump Temple Piece` count items into game collectible RAM.
- Hard-mode Stump-style rewards and A-C junk rewards should be detected by expected junk deltas tied to an exact current-level snapshot.
- Sync Mirror/Normal results only at safe post-level/exit moments; do not treat `8049D96B` as a simple permanent Mirror boolean.
- Use the marble popup guard while in-level/result transitions to prevent repeated vanilla unlock popups.

### Separate AP logical state from vanilla RAM state

Core design principle:

```text
AP inventory / AP checked locations are the authority.
Vanilla RAM flags are only the current physical representation needed to make the game behave.
```

This is especially important for:
- L11 State `3`
- Junk Factory visibility
- Submarine / Rocket Ship flags
- A-C level unlocks
- Marble unlocks
- Figure Roller Head unlocks
- Recipe/object unlocks if randomized

### Do not write these as AP received items

```text
Green Gem flags
Stump Temple Piece flags
Trophy flags
Collectible/check flags in general
```

Reason:
- They are check/location flags.
- Writing them can falsely complete locations.
- Green/Stump totals can update immediately when these flags are changed.

### AP-owned unlock flags

The following should generally be enforced from AP inventory if randomized:

```text
Marble unlock flags:              804DF36E-804DF381
Figure Roller Head unlock flags:  804DF521-804DF52A
Worlds A-C level State flags
Recipe unlock flags:              confirmed subset in 804DF4E0-804DF4FC, not a full continuous range
Recipe/object output flags:       804DF55C-804DF57E, do not use as received recipe unlocks
Vehicle cutscene gates:           804DF903 Easy, 804DF908 Normal, use 15/31/79/95 based on AP-authorized W5/W6 vehicle-side progression
Mirror Mode flag:                 804DF5F3, if used as cosmetic/filler
Hard Mode visible unlock flag:    804DF5F4, if Hard Mode is AP-gated/cosmetic-gated
```

Vanilla may briefly unlock these due to trophy counts, Green Crystal counts, Ant counts, level clears, or cheat codes.
AP enforcement should remove disallowed unlocks afterward. This may not fully suppress visible vanilla popup messages unless the popup/notification queue is later found.

### Be careful with junk counts

Junk/Vehicle saved counts can decrease or be cleared.
They are not safe one-way AP location flags by default.

If AP sends junk items:
- Track AP-caused writes.
- Suppress those increases from indirect reward/check detection.
- Write both the live/current count (`804DF4A2+`) and saved/persistent count (`9046F74E+`), otherwise the Junk Factory may not see the AP-sent inventory.

### L11 States are physical vanilla switches, not AP truth

Do not use `L11 State == 3` alone as a location detector.

Updated policy after the yellow-context hypothesis was invalidated:
- Do not use the old yellow-crystal value for L11 gating.
- Do not perform aggressive L11 cleanup while `in_level == True`.
- L11 completion should be detected through Trophy/extra flags/real completion side effects/AP-side shadow state, not State alone.
- If vanilla freshly unlocks next-world L1-L5 from a real L11 completion, undo only fresh `1` states when AP has not granted that world.
- If future testing finds a real screen/menu state, use it for UI-only `State=3` display behavior; until then prefer conservative outside-level cleanup.

### Suppress vanilla next-world unlocks

A real L11 completion can unlock the first five levels of the next world.
In AP, this must not grant world access by itself.

Rule:
- If vanilla sets next-world L1-L5 to `1` after an L11 completion, revert those `1` values to `0` unless the corresponding AP World Access item has been received.
- Do not lower `2` or `3` during this cleanup.

### Never create unsafe vehicle entry states

Known vehicle flags:

```text
804DF57F = Submarine
804DF580 = Rocket Ship
```

Risk:
- These can make W5/W6 enterable even if no levels inside the world are unlocked.
- Entering a world with no unlocked levels can crash the game.

Default rule:
- Do not write vehicle flags alone.
- Always also guarantee safe target-world starting levels if the vehicle item is meant to grant access.

Split vehicle/world access YAML option:
- If vehicle requirements are separated from world access, store AP vehicle ownership logically.
- Only expose the physical Submarine/Rocket Ship RAM flag on World Map / entry contexts when the player also has the matching AP world access.

### Save Slot 3 write safety

Known selected save slot address:

```text
8049D99F = selected save-file index
0 = Slot 1
1 = Slot 2
2 = Slot 3
```

AP target slot is Slot 3. The client can use this as a safety/menu heuristic:

```python
AP_SAVE_SLOT_INDEX = 2
SELECTED_SAVE_SLOT = 0x8049D99F


def ap_slot_selected():
    return read_u8(SELECTED_SAVE_SLOT) == AP_SAVE_SLOT_INDEX
```

Recommended behavior:
- Warn/refuse writes in save-file selection/menu contexts if `8049D99F != 2`.
- Do not treat this address as the only proof of active loaded save memory until the save-slot loading model is fully verified.

### AP World Unlocks should remain authoritative

Vanilla progression can attempt to bypass AP logic via:
- L11 State `3`
- real L11 completion unlock batches
- vehicle flags
- Green Crystal / Trophy / Ant count unlocks

The client must continuously enforce AP-owned access/unlock state in safe contexts.

---
## 14. Most Important Next Research Targets

1. **Confirm Easy and Hard address predictions**
   - Confirm Easy W1L1/W1L2 surrounding structure and whether Easy Green/Stump formula fully matches Normal.
   - Confirm additional Hard anchors beyond W1L1, especially Hard W1L2 and Hard W2L1.
   - Confirm whether Hard L11 levels have no Ant or use a different reward/check structure.

2. **Map indirect junk reward checks**
   - Map expected junk rewards for every Hard Stump-style pickup.
   - Map expected junk rewards for all A-C indirect Stump/junk reward locations.
   - Verify AP-caused junk writes are correctly ignored by indirect check detection.

3. **Find safer screen/menu state flags**
   - Find real screen/menu state for Level Select, World Map, Anthony's House, Result screen, and Difficulty Select if needed for safer UI gating.
   - Keep the old yellow-crystal value documented only as deprecated/unsafe.

4. **Mirror mode/result mapping**
   - Find a clean Mirror-enable address separate from Mirror result/trophy storage, if one exists.
   - Find full Mirror result slot mapping for all levels or determine if slots are dynamically reused.
   - Verify Mirror/Normal trophy and best-time sync on controlled level-exit events.

5. **Marble and Figure Roller selection safety**
   - Find equipped/selected marble address.
   - Find equipped/selected Figure Roller head address.
   - If AP locks an equipped marble/head, switch to an allowed one before removing the physical unlock.

6. **L11 and world-progression cleanup**
   - Test W1L11 / Junk Factory separation thoroughly without relying on the deprecated yellow value.
   - Confirm exact next-world L1-L5 unlock batches for L11 completions.
   - Ensure fresh vanilla unlocks can be undone safely without lowering played/completed states.

7. **Vehicle and Hard Mode persistence**
   - Confirm W6 L1-L5 state addresses in practice for Rocket Ship unlock behavior.
   - Confirm exact persistence path for `804DF5F4` Hard Mode visible/unlock flag.
   - Decide final YAML defaults for `hard_mode_unlock` and split vehicle/world access.

8. **Wii Balance Board checks**
   - Confirm `8049D945 == 14` across all Wii Balance Board level select and in-level states.
   - Verify transient goal detector behavior across many BB levels, restarts, and exits.
   - Optionally map direct BB completion flags if a Wii Balance Board is used.

9. **Trap safety**
   - Stability-test `80490A42` Blackout Trap in normal levels, Hard levels, A-C, W7, and Wii Balance Board levels.
   - Confirm that enforcing `80490A42 = 3` for 10 seconds does not break result/save/menu transitions if the player reaches the goal during the trap.

## 15. Mirror Mode / Mirror Result Sync

### Mirror mode / result-slot behavior

Address `8049D96B` was first found to affect Mirror mode:
- Setting it to `1` outside a level can make levels load in Mirror mode from the normal world-map campaign.
- Setting it while already inside a level appears to invert controls only, without reloading/mirroring the stage geometry.

Later testing showed this address is not a simple global Mirror flag:
- Easy W1L2 normal/non-Mirror Trophy is `804CA83C`.
- Easy W1L2 Mirror Trophy/result slot was observed at `8049D96B`.

Therefore treat `8049D96B` as a context-dependent Mirror/result slot or active Mirror setting, not a safe simple boolean.

### Mirror trap design status

Mirror Trap remains interesting, but should be treated as experimental/unsafe until a cleaner Mirror-enable address is found.

Avoid:
- blindly writing `0` to `8049D96B` after a timer,
- writing it every frame,
- writing it during result/save transitions.

Safer temporary rule:
- If used as a trap, set Mirror only at a controlled time before level load.
- Do not clear it during result/save contexts.
- Prefer syncing Mirror results back to normal results instead of relying on Mirror leaderboard slots for AP progression.

### Normal/Mirror trophy and best-time sync

User goal:
- If a trophy/best time is saved to a Mirror slot, sync it to the corresponding normal slot.
- If the normal slot has a better result, sync it back to the Mirror slot where appropriate.

Trophy order is confirmed:

| Value | Trophy |
|---:|---|
| `0` | none |
| `1` | Bronze |
| `2` | Silver |
| `3` | Gold |
| `4` | Platinum |

Higher trophy value is better.
Best time uses `Trophy + 0x06` as u16 big-endian milliseconds; lower valid time is better.

Sync only after a controlled event such as level exit / post-level transition for the current level snapshot, not every frame.

```python
def sync_trophy(normal_trophy_addr, mirror_trophy_addr):
    normal = read_u8(normal_trophy_addr)
    mirror = read_u8(mirror_trophy_addr)
    best = max(normal, mirror)

    if normal != best:
        write_u8(normal_trophy_addr, best)
    if mirror != best:
        write_u8(mirror_trophy_addr, best)


def is_valid_best_time(ms):
    # 0 and 0xFFFF are likely no-time/unset candidates; verify per slot.
    return 0 < ms < 0xFFFF


def sync_best_time(normal_trophy_addr, mirror_trophy_addr):
    normal_addr = normal_trophy_addr + 0x06
    mirror_addr = mirror_trophy_addr + 0x06
    normal_ms = read_u16_be(normal_addr)
    mirror_ms = read_u16_be(mirror_addr)

    normal_valid = is_valid_best_time(normal_ms)
    mirror_valid = is_valid_best_time(mirror_ms)

    if normal_valid and mirror_valid:
        best = min(normal_ms, mirror_ms)
    elif normal_valid:
        best = normal_ms
    elif mirror_valid:
        best = mirror_ms
    else:
        return

    if normal_ms != best:
        write_u16_be(normal_addr, best)
    if mirror_ms != best:
        write_u16_be(mirror_addr, best)


def sync_normal_mirror_result(normal_trophy_addr, mirror_trophy_addr):
    sync_trophy(normal_trophy_addr, mirror_trophy_addr)
    sync_best_time(normal_trophy_addr, mirror_trophy_addr)
```

Known example:

```python
EASY_W1L2_NORMAL_TROPHY = 0x804CA83C
EASY_W1L2_MIRROR_TROPHY = 0x8049D96B  # context-dependent; handle carefully
```

---

## 16. Miscellaneous Unlock Flags

### Mirror Mode

Mirror Mode unlock address:

```text
804DF5F3 = Mirror Mode unlock
```

Notes:
- Mirror Mode is only available in Free Play.
- It is currently not important for AP progression.
- Possible later uses: cosmetic/filler item, optional fun toggle, or ignored entirely.

### Hard Mode

Visible Hard Mode unlock address:

```text
804DF5F4 = Hard Mode visible/unlock flag
```

Important persistence / save behavior:
- `804DF5F4` is the value that visibly controls Hard Mode availability in the difficulty selection.
- Directly writing only `804DF5F4 = 1` can be temporary if no save happens afterward: the game may reset it back to `0` after returning to save-slot selection or after restarting.
- If `804DF5F4` is manually set to `1` and the game then saves somehow, the value can become persistent enough that it no longer resets to `0` when returning to save-slot selection or restarting.
- User observed that Hard Mode can remain persistently unlocked even if there is no obvious save after the credits. Therefore the exact save timing/source still needs more testing; do not assume the only persistence path is "credits watched + explicit post-credits save".
- Earlier observation still stands: after a real W7L10 completion / credits flow, Hard Mode becomes normally available and the game may restore the visible Hard Mode flag again later.

Additional values observed after the real W7L10 / credits / postgame unlock flow:

```text
804CA77F = 1
804DF5E9 = 1
804DF5EA = 1
804DF5EE = 1
804DF5EF = 1
804DF5F4 = 1  # visible Hard Mode flag
```

Current interpretation:
- `804DF5F4` is the visible/usable Hard Mode availability flag and may also be save-backed if the game saves while it is `1`.
- `804CA77F`, `804DF5E9`, `804DF5EA`, `804DF5EE`, and `804DF5EF` are set by the real postgame unlock flow, but setting those values alone does **not** unlock Hard difficulty in the difficulty selection. They are probably related to credits/postgame/other unlock bookkeeping or UI state.
- After the postgame/credits unlock flow, if W7L10 State is manually changed away from `3`, the game can automatically restore W7L10 State to `3` when returning to save-slot selection.

AP implication:
- For AP, treat `804DF5F4` as an **AP-owned unlock flag**.
- The client should continuously enforce the allowed value depending on AP inventory:

```python
HARD_MODE_FLAG = 0x804DF5F4


def enforce_hard_mode():
    allowed = has_ap_item("Hard Mode")
    wanted = 1 if allowed else 0
    if read_u8(HARD_MODE_FLAG) != wanted:
        write_u8(HARD_MODE_FLAG, wanted)
```

- If AP has not granted Hard Mode, suppress `804DF5F4` back to `0`, even if vanilla/postgame/credits flow or a save tries to make it persistent.
- If AP has granted Hard Mode, keep `804DF5F4 = 1`; if the game saves afterward, this may also make the unlock persist in the save file.
- If Hard Mode is AP-gated, postgame W7L10/credits behavior may still need cleanup because the game can also restore W7L10 State to `3` independently.
- Do not rely on `804CA77F`, `804DF5E9`, `804DF5EA`, `804DF5EE`, or `804DF5EF` as the direct Hard Mode unlock unless later testing proves they are needed in combination.

Open tasks:
- Confirm exactly when `804DF5F4` is written to save data after a manual write.
- Confirm whether the game saves `804DF5F4` directly or derives it from another persistent postgame flag on load/save-slot selection.
- Test whether returning to save-slot selection, normal saves, post-level saves, and post-credits flows differ for `804DF5F4` persistence.
- Test whether suppressing `804DF5F4 = 0` is enough to hide Hard Mode after real W7L10 / credits flow, or whether the client must also suppress another source flag.
- Decide whether Hard Mode should be AP progression, an option-gated mode, cosmetic/filler, or left vanilla.

---

## 17. Traps and Visual/Input Effect Candidates

### Blackout Trap / blindness effect

Address:

```text
80490A42 = screen wipe / blackout visual effect candidate
```

Observed values:

| Value | Behavior |
|---:|---|
| `0` | normal / no blackout |
| `1` | behaves like normal; pressing A/1 can set this value |
| `2` | small circle in the middle, then quickly switches to `3` |
| `3` | screen covered / blackout / blindness effect |
| `4+` | behaves like normal / no blackout |

Trap design:
- Item name: `Blackout Trap`.
- Classification: `trap`.
- Default duration: **10 seconds**, because the effect is very strong.
- Do not simulate A/1 button presses; the observed candidate values differ per level and are unsafe.
- While the trap is active and safe gameplay is active, continuously enforce `80490A42 = 3` rather than writing it only once.
- Safe gameplay currently means: inside a level, `804881AF == 1`, the transient goal detector is not active, and `8048D1B5` is not `94` / `95`.
- The timer should only tick during safe active gameplay. Menus, loading, goal/result, and unsafe transitions pause the remaining trap time.
- Outside safe gameplay, if the client owns the effect and `80490A42 == 3`, write `0` to hide the effect. Do not consume/clear the remaining timer merely because the player is in a menu or result screen.
- At goal, force `80490A42 = 0`; stale `3` values can persist visually until A is pressed in some edge cases.
- Continue enforcement during safe gameplay even if the player presses A/1 or dies/restarts inside the level, because those actions may reset the value to `0`/`1`.

Recommended implementation:

```python
BLACKOUT_EFFECT = 0x80490A42
BLACKOUT_DURATION_SECONDS = 10.0

blackout_remaining = 0.0
blackout_last_tick = 0.0
blackout_owned = False


def receive_blackout_trap():
    global blackout_remaining, blackout_last_tick, blackout_owned
    blackout_remaining += BLACKOUT_DURATION_SECONDS
    blackout_last_tick = time.monotonic()
    blackout_owned = True


def safe_gameplay():
    return (
        is_in_level()
        and read_u8(0x804881AF) == 1
        and not transient_goal_active()
        and read_u8(0x8048D1B5) not in (94, 95)
    )


def enforce_blackout_trap():
    global blackout_remaining, blackout_last_tick, blackout_owned
    now = time.monotonic()

    if blackout_owned and safe_gameplay() and blackout_remaining > 0:
        elapsed = max(0.0, now - blackout_last_tick)
        blackout_remaining = max(0.0, blackout_remaining - elapsed)
        blackout_last_tick = now
        write_u8_if_changed(BLACKOUT_EFFECT, 3)
        return

    blackout_last_tick = now
    if blackout_owned and read_u8(BLACKOUT_EFFECT) == 3:
        write_u8(BLACKOUT_EFFECT, 0)
    if blackout_remaining <= 0:
        blackout_owned = False
```

### A/1 press candidate values — rejected for input simulation

User tested addresses that change when pressing A or 1 depending on Wii Remote orientation.

Observed example values:

```python
A_PRESS_CANDIDATES_EXAMPLE = {
    0x804909F8: 128,
    0x804909F9: 135,
    0x804909FA: 40,
    0x804909FB: 224,
    0x80490A42: 1,

    0x807ABCBA: 188,
    0x807ABCBB: 200,
    0x807ABCDD: 121,
    0x807ABCDE: 189,
    0x807ABCDF: 155,
    0x807ABCEF: 176,  # verify exact final address if needed
}
```

Conclusion:
- Do not use these to simulate A/1 presses.
- Values appear level/context-dependent and therefore unsafe.
- The only current AP use from this test is that `80490A42` can be changed by A/1, so Blackout Trap must continuously enforce `3` while active.

### Noclip Trap / collision toggle

Address:

```text
80CBD6EB = collision toggle
```

Observed values:

| Value | Behavior |
|---:|---|
| `0` | collision disabled; player falls through geometry |
| `1` | normal collision |

Trap design:
- Item name: `Noclip Trap`.
- Classification: `trap`.
- Keep duration very short, around 3 seconds.
- Only activate during safe active gameplay inside a level, not during goal/result/menu states.
- Restore `80CBD6EB = 1` whenever the trap ends, the player reaches the goal, or the player leaves safe gameplay.

### Reset Trap candidate - rejected for now

Address:

```text
807AC8C1 = reset/cutscene candidate
```

Observed behavior:
- Setting `807AC8C1 = 32` can play a small cutscene and reset the player in W1L1 Normal.
- Later testing suggested this behavior was specific to W1L1 Normal, so this is not currently safe as a generic AP trap.

Rejected / hold status:
- Do not add `Reset Trap` to the normal AP trap pool yet.
- If revisited later, test multiple difficulties, normal worlds, bonus worlds, W7, tutorials, and Wii Balance Board before using it.
- Also ensure `80490A42` Blackout/wipe is forced to `0` while in the goal, because stale wipe value `3` can persist until A is pressed in some edge cases.


---

## 19. 2026-07-11 Update — Third-Party Address Table Reconciliation, Stage IDs, Mode Flags, Crystal Sanity Prep

This section records the newer third-party address-table data and how it compares with the addresses found directly in the AP mapping session.

Important notation rule:
- The third-party tables often write MEM1 addresses without the `0x80000000` base.
- Example: table address `0x4881AF` should usually be tested as `0x804881AF` in Dolphin/PPC address notation.
- NTSC and PAL addresses must not be mixed. NTSC addresses are useful only as hints for what kind of value to search for.
- Some PAL table addresses may refer to Save Slot 1, while this AP project targets Save Slot 3.

### 19.1 Data-size notes: why some values were searched as bytes

The table uses value types such as `8-bit`, `16-bit BE`, `32-bit BE`, and `Float BE`.

Meaning:

```text
8-bit / byte   = one byte
16-bit BE      = two bytes, big-endian
32-bit BE      = four bytes, big-endian
Float BE       = four bytes interpreted as a big-endian float
```

Why byte searches were still useful:
- Many gameplay flags are effectively small `0/1/2/3` values and can be found quickly as bytes.
- Big-endian `u32(1)` is stored as `00 00 00 01`, so the last byte often changes `0 -> 1` and is enough for simple flag observation.
- The known Green/Stump/Ant collectible bytes are examples where byte-level monitoring works well.

When byte searches are not enough:
- Stage IDs go above `0xFF` and should be read as `16-bit BE`.
- Crystal counts and some counters are documented as `32-bit BE`.
- Player coordinates and timers may be floats.

Helper functions:

```python
def read_u16_be(addr):
    return (read_u8(addr) << 8) | read_u8(addr + 1)


def read_u32_be(addr):
    return (
        (read_u8(addr) << 24)
        | (read_u8(addr + 1) << 16)
        | (read_u8(addr + 2) << 8)
        | read_u8(addr + 3)
    )
```

### 19.2 Region code

Third-party table:

```text
0x0000 [ASCII] Region Code
RK6E18 = NTSC
RK6P18 = PAL
```

In full PPC/MEM1 notation this is likely at `0x80000000` and should be read as a 6-byte ASCII game ID, not only a 32-bit value.

```python
REGION_CODE_ASCII = 0x80000000  # expected: b"RK6P18" for PAL target
```

AP use:
- Verify the connected game is `RK6P18` before enabling the PAL client.
- Refuse or warn on `RK6E18` because NTSC addresses differ.

### 19.3 PAL Stage ID addresses: World Map vs Free Mode

New PAL candidates from third-party table:

```python
PAL_FREE_MODE_STAGE_ID = 0x80474ACB  # 16-bit BE, table: 0x474ACB
PAL_WORLD_MAP_STAGE_ID = 0x80474B2E  # 16-bit BE, table: 0x474B2E
```

NTSC world-map candidate from third-party table:

```python
NTSC_WORLD_MAP_STAGE_ID = 0x8046F92E  # 16-bit BE, table: 0x46F92E
```

Use only the PAL addresses for RK6P18.

Important alignment note:
- `0x80474ACB` is an odd address for a 16-bit value.
- Test `0x80474ACA`, `0x80474ACB`, and `0x80474ACC` if DME/Python reads look strange.

### 19.4 Stage ID formula for W1-W7

The stage-ID table orders difficulties as **Normal, Easy, Hard**, which differs from the live difficulty index addresses:

```text
Live difficulty values:
0 = Easy
1 = Normal
2 = Hard

Stage-ID diff offsets:
Normal = +0
Easy   = +1
Hard   = +2
```

World bases:

```python
STAGE_ID_WORLD_BASE = {
    0: 0x01,  # W1 / The Empty Lot
    1: 0x22,  # W2 / Neighbor's House
    2: 0x43,  # W3 / Sizzlin' Desert
    3: 0x64,  # W4 / Chill Mountain
    4: 0x85,  # W5 / Ocean Treasure
    5: 0xA6,  # W6 / Space Station
    6: 0xC7,  # W7 / Stump Temple
}

DIFFICULTY_TO_STAGE_ID_OFFSET = {
    0: 1,  # Easy
    1: 0,  # Normal
    2: 2,  # Hard
}


def expected_stage_id(world_idx, level_idx, difficulty):
    return STAGE_ID_WORLD_BASE[world_idx] + level_idx * 3 + DIFFICULTY_TO_STAGE_ID_OFFSET[difficulty]
```

Examples:

```text
W1L1 Normal = 0x01
W1L1 Easy   = 0x02
W1L1 Hard   = 0x03
W2L1 Normal = 0x22
W7L10 Hard  = 0xE4
```

Use as a cross-check alongside the already-found live identity fields:

```python
WORLD_OR_MODE_INDEX = 0x8049D945
SELECTED_STAGE_INDEX = 0x8049D94D
DIFFICULTY_A = 0x8049D95D
DIFFICULTY_B = 0x804E0DF8
```

Recommended source-aware check policy:

```text
Current Game Mode == World Map Stage:
    allow AP checks
Current Game Mode == Free Mode Stage:
    ignore AP checks by default, unless YAML allow_free_mode_checks is enabled
Tutorials:
    ignore AP checks by default
```

### 19.5 Stage ID table typos / omissions in third-party paste

The pasted table is useful, but should be corrected by formula rather than copied blindly.

Likely issues:

```text
0x0F should likely be The Empty Lot 05 Hard, not The Empty Lot 04 Hard.
0x75 should likely be Chill Mountain 06 Hard but is omitted.
0xFB should likely be Haunted House 03 but is omitted.
0x10D should likely be City 01 but is omitted.
```

### 19.6 Bonus-world Stage IDs and Hard-only variants

Bonus IDs begin at `0xE5`.

User clarification:
- Candy Island 2 exists only on Hard difficulty.
- Haunted House Darkness exists only on Hard difficulty.
- Night City exists only on Hard difficulty.

Interpretation:

```text
Candy Island          = Easy/Normal-style bonus world
Candy Island 2        = Hard-only variant
Haunted House         = Easy/Normal-style bonus world
Haunted House Darkness = Hard-only variant
City                  = Easy/Normal-style bonus world
Night City            = Hard-only variant
```

This may explain the previously observed A-C blocks and the unknown/gap block. Do not assume A-C are only one shared Easy/Normal block anymore; Hard-only variants need mapping.

Research targets:
- Determine which save blocks correspond to Candy Island / Candy Island 2.
- Determine which save blocks correspond to Haunted House / Haunted House Darkness.
- Determine which save blocks correspond to City / Night City.
- Determine whether the previously documented unknown gap block is one of these Hard-only variants.

### 19.7 Player coordinates

Third-party PAL coordinates:

```python
PAL_PLAYER_X = 0x804874B0  # Float BE
PAL_PLAYER_Y = 0x804874B4  # Float BE
PAL_PLAYER_Z = 0x804874B8  # Float BE
```

Third-party NTSC coordinates:

```python
NTSC_PLAYER_X = 0x80488114  # Float BE
NTSC_PLAYER_Z = 0x80488118  # Float BE
NTSC_PLAYER_Y = 0x8048811C  # Float BE
```

PAL coordinates are useful for debugging/tracking position, but are not core AP progression data right now.

### 19.8 Simple in-level indicator candidate

Third-party table:

```python
IN_GAME_INDICATOR = 0x804881AF  # 8-bit
# 0x00 = in menu
# 0x01 = in level
```

This address was already in the 137-address combined in-level candidate group. If runtime testing confirms stability, it may become a primary simple in-level flag, with the combined detector retained as a fallback.

Recommended:

```python
def is_in_level_simple():
    return read_u8(0x804881AF) == 1
```

Test it against:
- normal World Map levels
- Free Mode levels
- Wii Balance Board levels
- level select
- result screen
- loading transitions
- death/restart

### 19.9 Stage Cleared Flag candidate

Third-party table:

```python
STAGE_CLEARED_FLAG = 0x8048D1B5  # 8-bit
# 0x7C = not cleared
# 0x5E = goal reached, stage cleared and data saved
# 0x5F = goal reached, stage cleared and data saved
```

This is distinct from the transient goal-reached candidate group. It may be a post-goal/save-state completion signal.

Critical Balance Board test:
- Check whether this flag changes to `0x5E/0x5F` when a Wii Balance Board level reaches the goal without a physical Wii Balance Board.
- If it does not change because data is not saved, keep using the transient goal-reached candidate group for Balance Board AP checks.

### 19.10 Current save-file addresses

Third-party table:

```python
CURRENT_SAVE_FILE_LOADED_CANDIDATE = 0x8049879F  # 8-bit, 0/1/2
```

Our direct find:

```python
SELECTED_SAVE_SLOT_MENU = 0x8049D99F  # 8-bit, 0/1/2
```

Hypothesis:
- `0x8049879F` may be the currently loaded/current save file.
- `0x8049D99F` may be the selected save slot in the save-file selection UI.

Need compare both across:
- save-slot select menu
- after loading Slot 3
- returning to title/save selection
- while in level
- while in Free Mode

AP safety should eventually require the active/loaded slot to be Slot 3 before writes.

### 19.11 Current Game Mode

Third-party table:

```python
CURRENT_GAME_MODE = 0x8049D96F  # 8-bit
# 0x19 = Free Mode Stage
# 0x1D = World Map Stage
# 0x1F = Tutorials
```

AP use:

```python
def is_world_map_stage():
    return read_u8(0x8049D96F) == 0x1D


def is_free_mode_stage():
    return read_u8(0x8049D96F) == 0x19


def is_tutorial_stage():
    return read_u8(0x8049D96F) == 0x1F
```

Recommended default:
- World Map Stage: allow AP progression checks.
- Free Mode Stage: ignore AP progression checks unless explicitly allowed by YAML.
- Tutorials: ignore AP progression checks.

### 19.12 PAL Save Data Arrays and Slot 3 confirmation

Third-party PAL save arrays:

```text
Slot 1 start = 0x8049DA14
Slot 2 start = 0x804B40D8
Slot 3 start = 0x804CA784
Slot stride  = 0x166C4
```

Slot 3 mode starts from table:

```text
Easy   start = 0x804CA784
Normal start = 0x804CDB40
Hard   start = 0x804D0EFC
```

These confirm our direct Slot 3 anchors:

```text
Normal W1L1 State = 0x804CDB40
Hard W1L1 State   = 0x804D0EFC
```

Confirmed Slot 3 unlockable blocks:

```python
SLOT3_MARBLES_START = 0x804DF36E
SLOT3_FIGURE_HEADS_START = 0x804DF521
```

These match our direct mapping exactly.

### 19.13 Record-offset conflict with third-party table

Third-party table claims, relative to a difficulty data start:

```text
+0x07 = Green Crystal / Lost Ant
+0x0B = Stage Trophy Earned
+0x10 = 32-bit BE Stage Best Time
```

Our direct mapping for Slot 3 Normal W1L1:

```text
State  = base + 0x00 = 0x804CDB40
Green  = base + 0x07 = 0x804CDB47
Stump  = base + 0x0B = 0x804CDB4B
Trophy = base + 0x0C = 0x804CDB4C
```

Our direct best-time observation for Normal W1L2:

```text
Trophy    = 0x804CDBF8
Best time = 0x804CDBFE/0x804CDBFF = Trophy + 0x06 = State + 0x12
Observed as u16 BE milliseconds:
17.33s -> 0x43B5 = 17333 ms
10.21s -> 0x27E8 = 10216 ms
6.63s  -> 0x19E9 = 6633 ms
```

Current interpretation:
- Prefer our directly tested offsets for AP client logic.
- The third-party `+0x0B Trophy` is likely off by one or omits/overlaps the Stump byte.
- The third-party `+0x10 Best Time 32-bit BE` may refer to a larger time field where the lower 16 bits at `State+0x12..+0x13` contain the observed millisecond value. Test before rewriting best-time sync logic.

Current preferred record layout:

```text
State      = base + 0x00
Green/Ant  = base + 0x07
Stump      = base + 0x0B  # Normal only; Hard Stump not persistent
Trophy     = base + 0x0C
Best Time  = base + 0x12  # observed u16 BE ms; possible larger field from +0x10
```

### 19.14 Persistent Mirror Mode candidate vs active/result Mirror slot

Third-party table says:

```python
SLOT3_MIRROR_MODE_CANDIDATE = 0x804DF5F3
```

Existing findings:
- `0x8049D96B` can act as an active Mirror-related slot / Mirror result slot; Easy W1L2 Mirror trophy was seen there.
- `0x804DF5F4` is the Hard Mode flag candidate from the previous mapping.

Interpretation:
- `0x804DF5F3` may be a persistent Mirror Mode unlock/option flag.
- Do not confuse it with the active Mirror/result slot at `0x8049D96B`.
- Test `0x804DF5F3` before using it in AP logic.

### 19.15 Current Hub Screen

Third-party table:

```python
CURRENT_HUB_SCREEN = 0x804E612F  # 8-bit
# 0x06 = Anthony's House
# 0x0A = Cheat Code Screen
# 0x0B = Options / Setup
# 0x11 = Tutorials
# 0x3F = Ranking
# 0xFF = Music Room / Screen Transitions
```

This can replace the deprecated yellow-crystal/context heuristic for several screen-gating tasks.

Important AP uses:
- Detect Anthony's House for W1L11/Junk Factory gating.
- Avoid writing sensitive state during transitions/music/ranking screens.
- Better separate menu contexts from level contexts.

### 19.16 Current Marble address

Third-party table:

```python
CURRENT_MARBLE = 0x804E6187  # 8-bit
```

Mapping:

```text
0x00 = Default / Marble
0x01 = Ladybug
0x02 = Cat
0x03 = Dog
0x04 = Pig
0x05 = Penguin
0x06 = Frog
0x07 = Rugby Ball
0x08 = Fishbowl
0x09 = Anglerfish
0x0A = Chick-N-Egg
0x0B = Baseball
0x0C = Bomb
0x0D = Earth
0x0E = UFO
0x0F = Saturn
0x10 = Broken TV
0x11 = Hedgehog
0x12 = Panda
0x13 = Figure Roller
```

AP use:
- If marble randomization locks the currently selected marble, switch to a valid AP-owned marble before enforcing locks.

Pseudo-code:

```python
def enforce_current_marble_allowed():
    current = read_u8(CURRENT_MARBLE)
    if not marble_index_allowed(current):
        write_u8(CURRENT_MARBLE, first_allowed_marble_index())
```

Needs testing:
- Whether writing this value changes the selected marble immediately.
- Whether it persists after menu/save/load.
- Whether locked selected marbles crash or fallback gracefully.

### 19.17 Timer and Crystal Count candidates

Third-party PAL table:

```python
PAL_STAGE_TIMER_OR_INGAME_TIMER = 0x8079CC30  # Float BE
PAL_STAGE_CRYSTAL_COUNT = 0x8079CC40          # 32-bit BE
```

Third-party NTSC table:

```python
NTSC_STAGE_TIMER = 0x8078ECF0
NTSC_STAGE_CRYSTAL_COUNT = 0x8078ED00
```

PAL `0x8079CC40` is especially important for optional Crystal Sanity.

Potential count-based Crystal Sanity logic:

```python
if current_level and crystal_sanity_enabled:
    count = read_u32_be(PAL_STAGE_CRYSTAL_COUNT)
    while highest_sent_crystal_for_attempt < count:
        highest_sent_crystal_for_attempt += 1
        send_check(f"{current_level.name} Crystal {highest_sent_crystal_for_attempt}")
```

Required tests:
- Does the count reset at level start?
- Does it increase immediately on each crystal pickup?
- Does it reset on death/restart?
- Does it include already-saved crystals or only current-attempt pickups?
- Does it work in Easy/Normal/Hard/A-C/Wii Balance Board?
- Does it count yellow crystals only, or other collectables too?
- Does it remain stable after goal/result?

### 19.18 Crystal Sanity YAML option

User proposed optional `crystal_sanity`, where every individual crystal in every level becomes an AP check.

Because the client can now identify current stage via `difficulty + world/mode + stage index`, and may have `PAL_STAGE_CRYSTAL_COUNT`, count-based Crystal Sanity is feasible.

Suggested option:

```yaml
crystal_sanity: off  # off / per_level_count
```

Future/advanced option:

```yaml
crystal_sanity: physical  # not implemented; would require per-crystal object IDs/flags
```

Recommended first implementation:
- Count-based sequential checks per level: `Level Crystal 1`, `Level Crystal 2`, etc.
- Do not attempt physical-position-specific crystal checks until individual object flags/IDs are found.

### 19.19 Temporary pickup/cache values — high-priority future search

User wants to find the temporary in-level values that cache pickups during the current attempt before they are saved/committed:

```text
Green Gem picked up this attempt
Stump Temple Piece picked up this attempt
Ant picked up this attempt
```

Why this matters:
- AP checks could trigger immediately on pickup rather than only after level completion/exit.
- It would be cleaner for player feedback.
- It may allow Hard-mode Stump Temple Piece checks and WA-C Stump/Junk-style checks without relying only on junk-delta or completion/exit logic.

Expected behavior:

```text
At level start: 0
On pickup: 1
On death/restart/exit: 0
On goal/save: copied/committed to save data if the game supports it
```

Search strategy:
- Compare before pickup vs after pickup before goal.
- Then restart/exit and filter candidates that reset.
- Repeat for Green, Stump, and Ant separately.
- For Hard Stump and A-C Stump-like rewards, also watch junk delta and current level identity.

### 19.20 Wii Balance Board AP tests still required

Known:

```python
BALANCE_BOARD_MODE_INDEX = 14
WORLD_OR_MODE_INDEX = 0x8049D945  # == 14 in Wii Balance Board level select and in BB levels
SELECTED_STAGE_INDEX = 0x8049D94D # 0-99 for BB levels
```

Balance Board levels:
- Have no normal collectibles.
- Vanilla completion flags appear to be set only when completed with a physical Wii Balance Board.
- AP checks should therefore use stage identity plus a goal/completion detector.

Current check plan:

```text
0x8049D945 == 14
+ 0x8049D94D == 0..99
+ transient goal reached this attempt
= send Wii Balance Board Level N check
```

Need test:
- Level 0 and level 99 index behavior.
- Goal detector in Balance Board levels.
- Restart/death/exit without goal sends no check.
- Goal then exit/result sends check once.
- No false positives in normal levels.
- Whether `0x8048D1B5` Stage Cleared Flag changes for BB without physical board.

### 19.21 L11 state tests still required

The L11 AP state-machine remains one of the highest-risk systems.

Need test:
- W1L11 / Junk Factory Access behavior using `CURRENT_HUB_SCREEN = 0x804E612F` instead of deprecated yellow-context heuristics.
- Level Select trophy display with L11 State `3`.
- World Map safety when L11 State `3` is suppressed.
- Vanilla next-world L1-L5 unlock suppression after real L11 completion.
- W4L11/W5L11/W6L11 interactions with vehicle/world progression.
- No crashy empty-world states after Submarine/Rocket/AP World Access combinations.

### 19.22 Updated address triage from third-party table

Directly useful / PAL, needs runtime verification:

```text
0x80474ACB Free Mode Stage ID, 16-bit BE
0x80474B2E World Map Stage ID, 16-bit BE
0x804874B0/B4/B8 PAL player coordinates, Float BE
0x804881AF In Game Indicator, 8-bit
0x8048D1B5 Stage Cleared Flag, 8-bit
0x8049879F Current Save File candidate, 8-bit
0x8049D96F Current Game Mode, 8-bit
0x804E612F Current Hub Screen, 8-bit
0x804E6187 Current Marble, 8-bit
0x8079CC30 In-game timer candidate, Float BE
0x8079CC40 Crystal Count candidate, 32-bit BE
```

Already confirmed by our direct tests / matching anchors:

```text
0x804CA784 Slot 3 Easy start
0x804CDB40 Slot 3 Normal start / Normal W1L1 State
0x804D0EFC Slot 3 Hard start / Hard W1L1 State
0x804DF36E Slot 3 marbles start
0x804DF521 Slot 3 Figure Roller heads start
```

Use cautiously:

```text
NTSC addresses
Slot 1/Slot 2 save-data addresses
Third-party record offsets that conflict with direct tests
0x804DF5F3 Mirror Mode candidate until tested
```

---

## 20. 2026-07-11 Updated High-Level Implementation Notes

### 20.1 Preferred current-stage identity stack

Use the strongest available combination rather than relying on a single value:

```python
WORLD_OR_MODE_INDEX      = 0x8049D945
SELECTED_STAGE_INDEX     = 0x8049D94D
DIFFICULTY_A             = 0x8049D95D
DIFFICULTY_B             = 0x804E0DF8
CURRENT_GAME_MODE        = 0x8049D96F
PAL_WORLD_MAP_STAGE_ID   = 0x80474B2E
PAL_FREE_MODE_STAGE_ID   = 0x80474ACB
IN_GAME_INDICATOR        = 0x804881AF
```

Default AP check gating:

```text
if not in_level:
    do not send level checks

if current_game_mode == World Map Stage:
    allow checks

if current_game_mode == Free Mode Stage:
    ignore checks unless YAML allow_free_mode_checks

if world_or_mode_index == 14:
    classify as Wii Balance Board stage, stage index 0-99
```

### 20.2 Deprecated yellow/context heuristic

The earlier yellow-crystal/context interpretation should remain deprecated. Use:

```text
0x804E612F Current Hub Screen
0x8049D96F Current Game Mode
0x804881AF In Game Indicator
0x8049D945 World/Mode Index
```

instead of the old yellow-context values wherever possible.

### 20.3 Current reminder list for next testing session

Remind the user to test:
- temporary Green/Stump/Ant pickup-cache values
- Wii Balance Board completions and test AP check sending
- L11 state handling/gating
- `0x8079CC40` crystal count for Crystal Sanity
- `0x8048D1B5` Stage Cleared Flag
- `0x804881AF` simple in-level flag
- `0x8049D96F` Current Game Mode
- `0x80474B2E` / `0x80474ACB` Stage IDs
- Hard-only A-C bonus variant save blocks

---

## 18. Source Split Notes This File Consolidates


Original split files:
- `kororinpa_general_notes.md` — high-level AP/RAM rules, save slot, read/write safety, unlock behavior.
- `kororinpa_world_specific_notes.md` — world block layout, W1-W7, A-C, world unlock behavior.
- `kororinpa_level_specific_notes.md` — formulas and address tables for levels/checks.
- `kororinpa_junk_fusion_specific_notes.md` — junk inventory formulas, recipe flags, vehicle updates.
- `kororinpa_chat_update_notes_2026-07-05.md` — latest chat discoveries.
- 2026-07-06 chat updates — L11 context-gated AP state-machine, Junk Factory separation, vehicle/world split option, marble order/unlocks, Figure Roller head order/unlocks, A-C vanilla unlock suppression, Mirror Mode flag, Hard Mode visible flag, save/persistence behavior, AP-owned Hard Mode enforcement policy, combined in-level detection, current-stage identity, Easy/Hard predicted tables, Hard Ant structure, indirect junk reward checks, AP-side Green/Stump counters, useful junk AP items, marble popup guard, Mirror/Normal result sync, selected save-slot index, Wii Balance Board mode/stage detection, transient goal-reached detector, Wii Balance Board AP check strategy, Blackout Trap, third-party PAL/NTSC address table reconciliation, PAL Free/World Stage IDs, Current Game Mode, Current Hub Screen, Current Marble, Crystal Count, Crystal Sanity planning, and updated TODO/test lists.
