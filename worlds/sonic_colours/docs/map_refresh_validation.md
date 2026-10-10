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

After the user reloaded the Grand World Map, world permission bits were unchanged
(Tropical Resort, Sweet Mountain and Aquarium Park enabled). The managed lock
sprite handle at Grand World Map actor +0xBC changed from `0x80AE53E0` to zero.
This is the second entry in the actor's +0xB0, stride-8 lock-sprite collection,
matching the code-derived world-index loop at `0x80264CE4`..`0x80264D58`.
Other actor differences include recreated resource handles and transient or
uninitialized fields; they are not candidate write addresses. A host write of
zero to +0xBC would bypass native managed-object release and is not implemented.
The immediate repair must update native scene-chain visibility and selection,
and release the affected lock sprite through its actual native lifecycle.

## Native refresh implementation (2026-10-11)

The client now queues one owned world's refresh in the exact installed C2
data block. Its request contains the current Grand World Map actor, zone and
selected native profile pointer/index. Production WritePolicy requires a bound
save, an attributed global-map context, the exact thunk and a currently granted
bank-A World Access bit. Actor and save memory are not host write targets.

The new `0x80266410` epilogue hook waits for interactive state **9**, confirmed
in the running Dolphin map on October 11. State 8 is the preceding scripted
transition. The hook follows the native `0x802671AC` lock lifecycle:
`0x805E7EE4` queues the lock animation, and `0x805E9D80(handle, 0)` releases
the actor's managed reference. It gets the existing scene root through its
native virtual method and applies `chain%02d_on/off` visibility using
`0x8026399C`, matching `0x80264524`. Terminal Velocity has no chain02..06 pair.
No whole-map initialization, cinematic queue or save-slot changes are invoked.

Boost/speed thunks now use STM/LM register preservation; prior exact payloads
remain accepted. Capsule executable instructions are unchanged. The combined
export retains one signature per directly called capsule routine and shares
the final conditional scope between controls and Medal capture. All four
enabled groups fit the standard handler (3256 bytes). Replace the complete
export, keep all four enabled, and restart emulation when testing this build.

Offline validation covers emitted PPC calls and ABI clobbers, each of six
worlds, invalid zones, changed profile/actor, transition deferral, duplicate
suppression, producer authorization, address/scene write rejection and exact
text normalization with an original capture. Existing capsule, White Boost,
speed, save, local-map and packaging regression tests also pass.

The live observation above verifies the current map state, not execution of
the new hook. Immediate lock disappearance, path visibility and selection
without leaving the map still require installing this build and a controlled
World Access delivery in Dolphin.
