# Swim/Breath PAL live investigation ? 2026-10-12

User selected Aquarium Park Act 4, native mission stg530. Read-only DME,
full PAL executable verification, player/controller owner checks; zero writes.

Dry sample: stats +8 = 00000100, +C = 0, +10 = 00000200;
current/pending native machine state 7. Underwater standing sample:
+8 = 0, +C = 00000420, +10 = 00200A00; current/pending 97.
User could perform one ordinary jump but not repeated upward strokes with
Double Jump absent. Existing native denial mailbox recorded request 8.
Thus the existing unconditional Double Jump request-8 gate also denies
underwater strokes. A production split needs native, actor-owned water checks
at request time, with Swim ownership independent of dry Double Jump; a slow
host-only mask substitution could briefly grant the wrong move at boundaries.

The old player+94 plugin-30 float remained zero and is not an oxygen timer.
Plugin 8075FEB8 at player+94 showed no changing clock in its first 80 bytes.
A float at the ability controller+24 changed by about one second per second,
but that does not prove oxygen ownership: constructor 800B033C initializes it
and it may be a shared state/ability clock. Do not write it as Breath.

Original native water/breath state strings are present (WATER_BREATH,
WATER_BREATH_AIR, CStateWaterBreathAir, CStateWaterBreath), with animation
references at 801F4DBC, 801F4E1C and related routines. Original 800381C4 is
just a flags getter, and 80088778 a generic bit setter. Neither proves the
buggy Swim Everywhere cheat is appropriate for Swim or Breath ownership.

Awaiting water-exit comparison and native oxygen countdown lifecycle proof.
No Swim/Breath feature certification or executable-memory writes were made.

## Reset and native drowning-music reference

User could not exit water without Double Jump, reset the stage, and reported
multiple natural drownings during the first observation period. The actor
therefore changed between observations; addresses must never be carried over.
Dry post-reset flags: stats +8=0, +C=00000400, +10=00000200.
Exact float indexing after reset: controller+24=1, +28?0.01,
+2C?48.43 on dry land. The earlier changing hex value was +2C, not +24;
it does not establish oxygen consumption and is not authorized for writing.

Original bgm_jingle_drown string at 8071F3A8 has a pointer at 808F1F8C.
Using original r13=808F9520, the load at 801F90B0 is lwz r5,-7594(r13).
801F9060's native member-state callback selects that cue on state-entry (-3),
with a Game Land alternative at -7590(r13), and dispatches through 80126554.
Related member-state logic uses an owner object with fields +E0/+E4 and an
embedded native sound handle +8C; its +E8/+EC also affect state selection.
These code-derived fields have NOT yet been bound to the current Sonic actor
or established as the elapsed oxygen countdown. Follow this original path;
do not substitute a nearby plugin float or the shared movement clock.

Next live comparison requested: temporary AP Double Jump for safe water exit,
then observe water entry/countdown and exit without allowing another drowning.

## Paused capture at visible countdown 4: owned oxygen clock resolved

The actual Water plugin is reachable through the owned request machine +34,
then the original 801066E8 linked collection: sentinel=collection+8,
first node=collection+C, next=node+4, object=node+8, name=object+8.
One CPluginStateInWater (name pointer 8071F010, vtable 807710FC) was found
among five current plugins, with a complete noncyclic traversal.

Native constructor 801F038C assigns that vtable. Oxygen clock is plugin+20.
801F0BAC..0BB8 increments it by the native frame delta. 801F125C returns
max(0,30-clock). 801F11E8 zeros it during the native reset path (called on
water entry and the replenishment path). Constants from original r2=808FC5C0:
808F8610 = 30.0 seconds, 808F8614 = 13.0 seconds. 801F0C10 compares remaining
air with 13 seconds before warning/notification. 801F0BB0 compares elapsed
with 30 before native drowning state request 100/101.

Paused live plugin clock was approximately 20.4336 seconds, remaining 9.5664.
The original warning notification uses message 5040, constructor 80059B94,
with remaining-time float at +14. This is separate from the generic 5015
integer timer notification investigated earlier, explaining why that earlier
sound/HUD cache did not show the visible underwater countdown digit.

client/water_native.py implements a bounded read-only owned-plugin resolver
and native oxygen math. Six tests cover values, cycles and class mismatches.
No oxygen writes or Swim/Breath behavior changes have yet been made. A no-Breath
entry can use a 17-second elapsed floor (30-13) to let the original warning
and drowning lifecycle run, rather than repeatedly restarting the countdown.
Native bubble/reset behavior still needs a controlled comparison.

## Live surface comparison

After the user resumed the paused countdown and surfaced using Double Jump,
the same live player had stats +10 = 00000240 (water bits cleared). Its
owned request-machine collection no longer contained CPluginStateInWater.
The native exit therefore removes the plugin; a cached plugin pointer must
never be reused after exit. Re-entry must resolve the collection again and
verify the new elapsed clock before any future Breath write is authorized.
No memory was changed during this comparison.

Re-entry live capture: owned Water plugin elapsed = 0.26666668 seconds,
remaining = 29.73333332 seconds, stats +10 = 00200A00. Thus re-entry starts
with the original 30-second supply, independently of the previous warning.
The new player address also differs from the surface capture; resolving
ownership each time is required across both plugin and player lifetimes.

## Test implementation

The movement payload now evaluates native stats bit 11 for request 8 inside
the guest. Wet requests use permission bit 7 (Swim); dry requests keep bit 0
(Double Jump). Existing owner, vtable and predecessor guards remain intact.
The replacement combined profile still occupies 3256 bytes. Four redundant
install comparisons on owner-gated speed/boost hooks are omitted only in this
combined export; full PAL text and installed payload verification remain
mandatory before any owner is armed. Ungated map/transition guards remain.

When Movement Unlocks is enabled and Breath is absent, the client floors a
fresh owned Water plugin's elapsed clock to 17.05 seconds. The native game
then sees remaining air below its 13-second warning threshold and handles
music, notification and eventual drowning itself. The floor does not restart
an active countdown. Native bubble resets receive the same shortened supply;
Breath ownership stops imposing the floor, preserving the current countdown
until the next native bubble/reset/entry. No forced death or executable write.
Actual Swim input and immediate music/countdown playback remain pending live
validation with this new build.
