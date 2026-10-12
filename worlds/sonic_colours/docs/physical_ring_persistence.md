# Immediate physical Red Ring collection

The client journals directly observed pickups before projecting their bits into
the PAL current-stage bitmap (actor-state vtable 8075A228, byte +91) and,
after save attribution, the selected save's physical collection flags
(320 + zone*30 + zero-based Act*5 + zero-based Ring).

Projection preserves unrelated bits, validates the current actor/save chain on
each write, and permits only journal-witnessed collection bits. AP Red Ring
counter items do not populate physical pickups. A fresh same-seed playthrough
uses a new bootstrap epoch and cannot inherit the preceding playthrough's
physical rings. Intro pickups are retained in the journal before slot selection;
their save flags are projected after the new save is safely attributed.

NAND autosaving remains under the original game's control. The journal restores
witnessed bits when the client resumes the attributed playthrough; this does not
claim an immediate native disk flush. Native transparency/World Map rendering
after death and level abort still require live Dolphin validation.

World item display names are now `<World> Shuttle`, with unchanged numeric IDs.
Discovery locations use `<Colour> <Ability> Discovery`. Their stage ownership is
TR Act 3 (Laser), SM Act 1 (Drill), SM Act 3 (Rocket), SC Act 1 (Cube), SC Act 5
(Hover), PW Act 1 (Spikes), AC Act 1 (Frenzy). The native colour-to-AP discovery
index conversion remains intact; this corrects region assignment, not native
colour numbering. Old server Discovery names are normalized by the client and
must still pass the exact enabled-location/ID validation.
