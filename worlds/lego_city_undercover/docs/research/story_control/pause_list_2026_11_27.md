# Original pause-list implementation

The visible six-row pause menu is an immediate-mode list. It is not the BAML
button pool, `MenuFlow2`, `GUI2Menu`, or the `PauseMenuDrawer` background renderer.
Earlier factory work based on those candidates did not identify this list.

## Confirmed source and live identities

Pinned EXE SHA-256: `624fed07274bbd105d1d571ecb97a290df6f6f0aff76898c516890da6d136f76`.

| Binding | RVA / layout | Evidence |
| --- | --- | --- |
| Draw callback | `0x80b090`, Win64 `void(context*)` | Called indirectly by `0x54ee7a` and by measurement `0x550327`; return ignored |
| Input callback | `0x80ab60`, Win64 `void(context*)` | `0x550a8f`; selection copied to context `+0x40`, confirm `+0x70`, back `+0x74` |
| Row draw | `0x8af760` -> `0x54f310` | context, UTF-8 text pointer; native row counter, positioning and highlight |
| Runtime records | `0x115d7c0`, stride `0x30` | `0x54f700` copies 42 game records after five engine records; total 47 |
| Pause record | runtime index 7, ID 2 | Live draw/input pointers match `0x80b090` / `0x80ab60` |
| Source records | `0x1176700` | Source index 2 is copied to runtime index 7; patching the source alone is ineffective |
| Contexts | `0x1c4c9f0`, ten records, stride `0xf0` | Native push, draw, measurement and input all use this array |
| Stack index | `0x115efc4` | Live index 1 points to record 7 with six rows |
| Record count | `0x115efe0` | Live 47 before installation, 48 after registration |
| Push / Back | `0x550140` / `0x54eca0` | Original native stack operations, with context remeasurement on return |

The language vector at `0x1190cd8` contains the exact live screenshot texts:
`0x21` Fortsetzen, `0x22` Optionen, `0x24` Extras, `0x2f` Zur Polizeistation
zurückkehren. The optional station action predicate `0x3d4b0` leads directly
to the matching draw and input callbacks.

## Implemented boundary

`native/pause_menu.h` registers an additional native record with ID `APCH`,
wraps only the original pause record's draw/input callbacks, and inserts
`Chapter Select` directly after Resume, above the station-return entry. Selecting
it pushes an original-engine submenu. All fifteen
English chapter labels belong to one scrolling list. Esc/controller Back uses
the original native return action; there is no separate Back row. After the user
found the initial reduced font too small, the layout was changed to match
original Extras: normal font 0.5, spacing -0.10664, selection centered and rows
fading between absolute Y 0.15 and 0.60. These constants and centering/fade
behavior come from `0x7f0a10` / `0x7f0f99`. Keyboard/controller navigation and measurement
remain native. The additional root row is intercepted before the vanilla
action dispatcher can consume its index.

The original root callback still generates every native optional entry once.
During that pass its Resume text is clipped with the native row bounds; the
remaining rows are drawn one position lower. Resume and Chapter Select are drawn
into the two reserved top positions using the native localized Resume string.
Visible selection indices below Chapter Select are translated by one only for
the vanilla input callback, then restored. The native fixture verifies both
text positions and routing of station/Options/Extras/quit selections. No global
text-renderer detour is installed.

Chapter labels are deliberately grey and do not start anything. Independent
chapter transactions, AP chapter permissions, native assignment admission
hooks and Open World initialization are **not implemented** by this UI change.
No completion, inventory, actor, achievement or save fields are written.

The bridge checks all six function prefixes, table identities and capacity;
unknown callback owners are rejected. Its resident module is pinned before
callbacks are published. Callbacks are updated with aligned atomic pointer
exchanges on the game window thread. Disabling retains the pinned dispatch
record but removes the additional row; disabling inside the submenu is rejected
until its normal Back action is used. A process restart removes the extension.

## Validation

The isolated native fixture verifies root-row measurement, preserving vanilla
actions, intercepting the additional row, all fifteen chapter rows, inert chapter
activation, native Back routing and disabled behavior. Prefixes were checked
against the pinned local EXE before live installation. Five related existing
Python tests passed.

Live installation in PID 5708 returned installed/enabled. Readback confirmed
the runtime table grew from 47 to 48 and record 7 points to the resident DLL.
The user confirmed the additional row is visible and opens the native submenu.
They then requested English and one page for all fifteen chapters, and confirmed
all rows were visible but too small. The requested Extras-style scrolling version
was built, tested and installed through a hash-verified handoff from the disabled
old bridge, without restarting the game. The user confirmed the scrolling layout
and requested removal of the redundant Back row; the list now contains only the
fifteen chapters, with Esc/controller Back still handled by the native input path.

Run `tools/configure_pause_menu.py` with the repository Python to install,
`--query` to inspect callback draw counts, or `--disable` after returning to
the root pause menu. The tool uses the manifest-pinned native bridge and never
attaches a debugger. `tools/probe_pause_list.py` is read-only.

The connected native client installs the menu once per loaded process after
save binding. Failure is logged without stopping checks or deliveries. This
does not enable chapter-start options in seeds. For development handoffs only,
`--replace-build <previous-manifest.json>` verifies the old DLL hash, loaded
module and all four callback owners, disables its UI, and requires the root
pause menu before replacing the registered tail record on the game thread.
