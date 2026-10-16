# Save selection and player-patch server address

The WebHost download route already fills `archipelago.json.server` from the
room's `last_port`. Downloads made before port allocation can contain null.
The generating APWorld cannot predict the later hosted room port, and local
changes cannot alter archipelago.gg's deployed download service.

The Launcher now uses an embedded address or explicit --connect. If neither
exists, its GUI requires the room's host:port and writes a separate official
`_connected.apsoniccolours` file. Existing files are never overwritten. The
headless client fails with instructions instead of using a previous room.
Offline --patch-only still works without an address. Start a hosted room before
downloading to have its website embed the address directly.

Save-selection HUD resources are now generated locally from ui_file_select's
Scene_GameData, preserving all four original animations and original casts.
The native map context's mode 6 identifies this screen. The original
application+4 -> document+58 -> service+10 observation was an allocator link,
not a stable UI owner; the next live test disproved it. The replacement native
font publisher registers its actual scene reference on the guest thread in
the reserved native ISO word 0x80002FBC. The extended resource controller uses
magic 0x41504845 and includes that reference at +16. Legacy Riivolution builds
do not write the native registry. Discovery verifies the added
350-cast layout, 90 AP mailboxes, publisher, controller and reference anchors.
The menu mode is anchored too, preventing writes after a scene switch.

46 focused tests passed before final endpoint/mode guard tightening. Visual
placement/layering on the rebuilt ISO still needs Dolphin verification; the
current running ISO does not contain these new save-select resources. Do not
claim a visible overlay based on the resource tests alone. No new seed needed.
