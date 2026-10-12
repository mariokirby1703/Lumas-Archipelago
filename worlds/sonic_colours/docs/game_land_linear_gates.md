# Linear Game Land gates

All 21 stages require AP Red Ring item value. Order: 1-1 through 7-1,
then 1-2 through 7-2, then 1-3 through 7-3. Requirements start at 1.
Integer step = max(1, floor((179 - reduction) / 20)). No rings are consumed.

| Reduction | Step | First / last requirement |
|---|---|---|
| 0 | 8 | 1 / 161 |
| 40 | 6 | 1 / 121 |
| 100 | 3 | 1 / 61 |
| 113 | 3 | 1 / 61 |
| 150 | 1 | 1 / 21 |
| 179 | 1 | 1 / 21 |

Integer rounding means nearby reduction values can produce the same sequence.
For 113, stages 1: 1,4,7,10,13,16,19; stages 2: 22,25,28,31,34,37,40;
stages 3: 43,46,49,52,55,58,61.

The world rules and PAL flag projection use the same generated thresholds.
The native gate bits are 210 + (world-1)*3 + (Act-1), including Act 1.
Game Land entry remains available; individual stages stay locked until their
AP value is met. Own Wisps/Shuttles are placed outside Game Land to avoid
ring-gated startup dependency cycles. Generation was checked for six option
sets at 100 seeds each, with all 180 reduction values checked for spacing.

Existing schema-7 server slot data with the exact prior threshold formula is
accepted without changing that seed. A new generated seed is required for
linear thresholds and locked first stages.

Vanilla unlock event publication is implemented in client/game_land_notice.py.
PAL 8016CB5C appends event type 2 through 8016CDA4 and sets flag 11.
The live Act-1 observation confirmed module+38 directly owns the 8076AC7C
object (the earlier additional +38 dereference was incorrect), its +1C parent
module, queue pointer = object+70, count 0, descriptor 80000005.

The client durably records false-to-owned gate transitions before projecting
permission bits, then publishes type 2 into the verified five-entry native
inline vector. It preserves the other entries and publishes count last.
Menus and full queues defer delivery. A durable publishing intent prevents
automatic duplicate animation after an uncertain write/crash. Save identity,
PAL revision, parent pointer, vector/count and expected values are revalidated
on each write. No fake physical rings, scene forcing or new Gecko code is used.
Native results/return controls event playback; queue publication is not proof
that the animation plays correctly. Actual live playback remains to be tested
by receiving enough AP Ring value in an attributed Story Act and finishing it.
