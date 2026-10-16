# Collapsed Game Land columns — 2026-10-17

Observed live on PAL SNCP8P Rev0, native seed digest
`80e0a477671b42151c7c5aee0b21ad18`: availability bits 210 and 213
correctly enabled 1-1 and 2-1. Stage selection owner state was 13.
The native `emerald_1` parent of all three second-column Acts retained
local scale (0,0). Its Act 2-1 world transform therefore collapsed to
the Emerald position, without displaying its text. Reloading rebuilt it.

`game_land_columns.targets` now resolves all seven named column parents
in the authenticated native selection layout. In settled stage selection
only, it unfolds a completely collapsed parent if at least one of its
Acts is already available. Locked columns, intermediate animation scales,
native scale overrides, intro and exit states remain untouched. No save,
availability, clear, rank, item, executable or music fields are written.

Local scale restoration alone is insufficient: native 805E5310 reuses
the local matrix when scale-validity bits 4/5 remain set. The repair clears
those bits and the world cache; descendants and ancestors receive their
corresponding transform/redraw invalidation. The existing guarded UI batch
anchors the owner, menu state, availability bank and pane topology, compares
every write, and publishes redraw markers after the data. Repeated polls
leave an already unfolded column unchanged.

Live bounded UI-only application, without reloading the menu, produced:

| Node | Before scale | Before Y | After scale | After Y |
| --- | --- | --- | --- | --- |
| emerald_1 parent | 0,0 | 205 | 1,1 | 205 |
| act_1_0 (2-1) | 0,0 | 205 | 1,1 | 241 |

The user tentatively confirmed the visible fix after moving left/right;
the native matrices above independently confirm the restored separation.
Cursor relocation was exercised through normal selection movement, not a
forced native call. Automatic repair on a future unlock and all seven
columns still need an additional end-to-end playthrough test.

This is a client-only correction: existing seeds and patched ISOs remain
usable. Restart the updated client to load it. No new seed or ISO needed.
