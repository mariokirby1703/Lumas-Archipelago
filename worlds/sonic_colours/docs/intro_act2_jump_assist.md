# Intro Act 2 jump-assist feasibility (2026-10-12)

Read-only PAL check; no actors, stage assets or saves were modified.

The photographed step is matched to stg130 / stg130_obj_00.orc / IronBox
object 6. Original placement: (11658.7002, -968.0, -9422.8096). Live Sonic
position on the crate: (11654.4189, -948.0, -9422.8125). The active crate actor
was 90CB0EC0, vtable 80778DC8, retained ORC record 90B630E8. These heap
addresses identify this capture only and must never be hardcoded.

Original Act-2 layout contains three Spring templates (107, 45, 48), each
with one placement. Their coordinates are respectively
(9231.5303,-590.0300,72.3300), (7609.1201,-620.0500,21.8500),
(7502.3501,-625.0500,21.8707). Native spring object data already exists;
no replacement artwork/assets would be needed for that object class.
The Spring actors were not present in the bounded active actor list at the
ledge, consistent with their distant placements; resource readiness for a
new instance at this location has not been proven by that observation.

JumpBoard object 122 is already present beyond the step at
(12357.7998,-750.0,-9422.8203), actor 90CCC9C0, vtable 8075F860. Static
JumpBoard constructor vtable initialization is at 800AE348. Moving that
board or a previous Spring would remove existing traversal assistance and
is not a proven substitute for adding a new instance.

The proposed addition is an independently registered native Spring on/near
IronBox 6, enabled only for the attributed mandatory New Game Act 2. It must
retain native ownership, model/collision creation, unique object identity,
range/lifecycle and cleanup and disappear for normal replay. No raw actor
copies, guessed pointers or persistent double-jump grants are acceptable.
Safe native creation/registration, orientation/launch parameters, and actual
landing clearance are still unresolved. This audit does not establish that
an added Spring works in Dolphin or that the entire intro is completable
without movement items. No access-rule changes were made, per user request.


## Implemented IronBox lift test build

The production runtime now checks an exact-owned main-layer ORC resource
using actor-wrapper ownership, original object ID/class hash/file offsets,
BINA/SOBJ headers, counts and exact original X/Z and bounded Y values. It
changes ONLY IronBox 6's instance Y from -968 to -948 (+20 world units),
before the target actor is created. Native creation supplies model and
collision; no actor, physics-body or save record is fabricated/copied.

Automatic activation requires movement_unlocks, an attributed mandatory
prologue and Act 2 before native save attribution. The write guard rejects
raising in normal replay. A cached raised resource is restored to original
placement on an attributed normal replay before actor creation. Existing
target actors are never moved: the status asks for an Act restart if changing
the placement would desynchronize already constructed model/physics. The
CPK on disk and Gecko instructions remain unchanged. No progression logic or
Double Jump permission is changed.

Test from the beginning of a properly attributed new-game prologue with the
new client already connected. /sonicstatus includes intro_box_assist; expected
status is raised native spawn placement / intro box raised, lift=20. At the
step, check that Sonic stands on the raised collision surface and can reach
the ledge with a SINGLE jump. If 20 units is insufficient or the first jump
onto the raised box becomes impossible, tune only after live measurements.
This is an implemented test build, not a claim of completed live traversal.


## Scope update: all attributed Act 2 visits

At the user's request, the placement lift now applies to every Act 2 visit
with movement_unlocks enabled, including normal bound-save replays. It no
longer requires mandatory-prologue state or an unselected save. Current
playthrough attribution, verified Act 2 ownership, exact ORC coordinates,
bounded +20 placement and refusal to move an already constructed actor all
remain enforced. Movement Randomization Off selects/restores the original
placement before construction. Enter Act 2 from the beginning with the new
client connected; a client restart alone cannot move an existing crate.
Traversal and collision remain pending live verification.


## Live height adjustment

User confirmed that the +20 placement visibly moved the crate, but reported
that a normal jump could not quite reach its top. Lift reduced to +15 for the
next test. The exact prior +20 value is accepted for cache migration only,
and still cannot be changed after actor construction. First-jump reach and
the second jump onto the ledge remain pending live validation.
