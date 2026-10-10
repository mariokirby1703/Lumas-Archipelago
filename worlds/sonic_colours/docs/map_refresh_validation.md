# Grand World Map and diagnostic rendering

The user observed Aquarium Park Access received on the Grand World Map did not
immediately remove its lock or permit selection. Entering and leaving Tropical
Resort's local map refreshed the Grand World Map and permitted Aquarium Park.
This establishes persistent ownership projection and a missing immediate global
map refresh, not a working immediate unlock. Clear/Rank transmission continued
to work according to the user's earlier observations.

Read-only live inspection identified map mode 2, active context `0x90AB6CC0`,
and Grand World Map actor `0x90B50220`, vtable `0x80777000`. Current production
map writers cover save permissions and local waypoint states only. They do not
refresh the global map's scene-resource paths and existing lock sprites.

PAL initialization uses `0x8026459C` for chain visibility and `0x80264C08` for
the world-lock sprites. `0x802638AC` changes scene-node visibility recursively;
lock sprites have managed ownership. Calling the full initializer again or
zeroing sprite handles would also affect event queues, selection state or
reference counts. No such mutation is introduced by this fix. Immediate Grand
World Map refresh remains unresolved, pending a guarded native update for both
paths/selection and managed lock-sprite removal. Leaving and re-entering the
global map remains the observed workaround.

The user also observed `/sonicstatus` becoming a very tall blank GUI rectangle
after client restart/reconnect. Previously each JSON document, including dozens
of rank records and native evidence, was one log record and one Kivy label.
The client now outputs diagnostics in records bounded to 1,800 characters and
12 newlines, preserving the complete JSON text in order. The same output path
covers `/sonic`, `/sonicstatus`, `/sonicdebug`, `/sonicitems` and `/sonicmusic`.
The shared Archipelago GUI is unchanged.

Automated tests verify exact content reconstruction for large nested evidence,
long strings and Unicode, plus status before and after runtime reconnect.
Actual Kivy rendering after reconnect still requires user validation. Neither
these tests nor the output fix establish an immediate native map refresh.
