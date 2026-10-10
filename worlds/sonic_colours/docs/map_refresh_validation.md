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
The initial split-record fix was rejected by the user because GUI copying acts
on individual records. Diagnostics now use one copyable JSON record with each
top-level field on its own line and compact nested values. `/sonic` and
`/sonicstatus` retain operational statuses, identity and counters, while directing
full native evidence to `/sonicdebug` and receipt history to `/sonicitems`.
The detailed commands also produce one record. The shared GUI is unchanged.

Automated tests verify single-record JSON content for large nested evidence,
long strings and Unicode, plus status before and after runtime reconnect and
full evidence retention through `/sonicdebug`.
Actual Kivy rendering after reconnect still requires user validation. Neither
these tests nor the output fix establish an immediate native map refresh.

The next controlled live comparison reproduced the issue with Sweet Mountain:
its native world permission (bank A bit 21) changed from false to true while
the same Grand World Map actor/context remained loaded. The user still saw the
lock and could not select the world before a map reload. Other denied World
Access bits remained false. The stale map actor was captured locally before
reload; no map/UI guest writes were performed.
