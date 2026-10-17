# Game Land percent slider and native effect settings (16 October 2026)

## Game Land Requirement Reduction

The player-facing range is now **0..99 percent** (default **50%**). The saved
option key remains `game_land_requirement_reduction`. For `options_revision >= 8`,
its integer value means percent, not absolute reduction points.

The conversion to the *existing* 0..179-point input is:

```python
old_reduction = (180 * percentage + 99) // 100
```

This gives 0% -> 0, 25% -> 45, 50% -> 90, 75% -> 135, and 99% -> 179.
Crucially, `game_land_gates(old_reduction)` and its 21 unlock calculations have
**not** changed. AP Red Ring item currency and the other Game Land features
are not affected.

`options_revision` is now **8**. Existing revisions **0..7** remain interpreted
using the original 0..179 *absolute reduction*, including values above 99.
The slot validator only accepts the new 0..99 percentage for new revision-8
slots and continues to authenticate the serialized exact gate table. Legacy
`1-1 = 1` exceptions remain restricted to old slot revisions.

New seeds must use the updated APWorld/client. Do **not** edit the option value
inside a generated `.apsoniccolours` file or change the rules on an existing
Archipelago server: the slot seed's item distribution and gate costs must match.

## DeathLink and Dead Weight

Both effects can now be chosen without the hidden `native_feature_tests` flag:

- `death_link: true` enables outgoing/incoming DeathLink (default `false`).
- `dead_weight_trap_weight: low` is the new default; `off`, `medium`, `high`
  are still valid. Trap generation still depends on `trap_percentage` and the
  remaining filler pool. "Low" does not guarantee a trap in every seed.
- The established native kill/temporary trap ACK, transaction, anti-echo and
  safe-state checks remain in place. There is no bypass in the memory writer.

**Safety status:** `data/versions.json` still reports `live_validation.deathlink`
and `live_validation.dead_weight` as `false`. Exposing the two options is a
user-requested experimental opt-in, **not** proof of completed PAL Dolphin
end-to-end validation. Check real gameplay, respawns, safe zones, reconnects,
DeathLink echo suppression, and dead-weight effect expiry before marking these
features as live-verified or recommending them for an important multiworld.
