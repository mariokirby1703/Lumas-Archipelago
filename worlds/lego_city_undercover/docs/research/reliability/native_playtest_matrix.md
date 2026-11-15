# Controlled native movement and receipt tests

Use an unused disposable slot and the automatic native backup. Existing valued saves must not be deleted/reset. Keep area rollback explicitly experimental. A successful RPC or generated seed does not mark a row successful.

Before boarding, stand and move normally on allowed Auburn ground so a separate foot anchor is captured. Remove Cherry's pass only through the explicitly scoped test override. Stay near the boundary (maximum 90 m return); do not begin with Fast Travel. Copy both Gebiet-Diagnose and Sammeldiagnose after each case. Record seed, game slot, EXE hash, DLL filename and the first failing phase.

| Case | Action | Required observations | This pass |
|---|---|---|---|
| Walking | Cross Auburn to Cherry without pass | request accepted; position changes; allowed district observed; controls/collision stable | not live tested; earlier user reported success |
| Running/jumping | Hold movement while repeatedly crossing, including a jump | busy states defer; repeated confirmed returns work; never replay uncertain command | not live tested |
| Car | Cross as driver; brake/steer after return | car/rider return together; no excessive momentum/clipping | not live tested |
| Motorcycle | Repeat with bike | rider remains attached; physics/control valid | not live tested |
| Bus/truck | Repeat with large road vehicle | correct footprint/collision; correct driver identity | not live tested |
| Boat | Approach a boundary over connected water | native water pose remains valid; boat and rider stay usable | not live tested |
| Plane/helicopter | Cross at controlled speed/height | returned aircraft remains airborne/usable; camera and control stable | not live tested |
| Hover/UFO | Repeat with actual hover class | correct native class; control/physics valid | not live tested |
| Passenger | Cross with an NPC driver | one native exit request; fresh unmounted observation; Chase at allowed foot anchor; vehicle left behind | not live tested |
| Tram/train | Cross aboard rail transport | exact model/seat detected; Chase-only foot recovery; route/consist untouched | not live tested; earlier user reported tram movement, not Chase-only exit |
| Changed/destroyed vehicle | Change vehicle or destroy it while denied | separate foot recovery; no stale old vehicle transform | not live tested |
| Pig | Ride across and continue riding afterward | GetRidden target stable; correct creature returns; rider/actions valid | not live tested |
| Behemoth | Cross during dinosaur takeover | correct actual target; takeover/story actions continue | not live tested |
| Dismount | Exit immediately after a requested return | old vehicle anchor cannot disable subsequent foot enforcement | not live tested; prior user bug has regression tests |
| Receive pass | Receive Cherry pass while denied/pending | permission takes effect without native ability/save flag dependency | not live tested |
| Reload locked | Load inside forbidden district with no anchor | explicit recovery message; no guessed/stale teleport | unsupported recovery; message tested |
| Fast Travel | Inspect destinations before attempting distant travel | a real pre-transition destination gate is required | native destination gate unsupported; do not test as guaranteed protection |

For every live row record separately: command accepted, requested/observed XYZ, district returned, rider/vehicle identity, controls tested, collision/physics tested, native save before/after, and operator verdict. Leave unknown fields unknown. `live_gameplay_verified` requires those gameplay checks, not only geometry.

For each progressive family, receive stage 1, verify class selection and absence of stage 2 tool, receive stage 2, verify tool, switch outfits, autosave/reload and reconnect. Repeat Criminal Scan/Detective Scan/Wiretap before Police and after Police arrives. Surveillance is a legacy-only flag, excluded from new pools. Verify old standalone IDs without changing their meanings.

For pickups, revisit a tile for at least two ordinary snapshots, collect a small and large brick, leave/re-enter, disconnect/reconnect, restart and replay a mission. Confirm source/type/bit evidence, exactly one outgoing check, correct persistent acknowledgment and no AP-grant token discovery. For mansion replays test both descriptor-named assignments independently.
