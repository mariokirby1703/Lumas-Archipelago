# Super Brick observation matching review

Latest supplied cumulative log is preserved as ignored
notes/analysis/user_monitor_superbrick_mapping_review.json. It contains 18 unique
Super Brick bit events, all 18 with evidence.location.player_position. Each event
also retains timestamp, native tile when resolved, bit index, byte offset, mask,
before/after byte and payload address. These are sampled actor coordinates at
detection, not an exact pickup-frame transform or the pickup object's coordinates.

Comparison against 471 source objects in city_superbricks.csv yields 17 close
spatial candidates (nearest <=0.8 units and separation to second nearest >=0.5).
These thresholds are an analysis heuristic, not proof of identity. Bit 372 is
unresolved: nearest source object is 3.391 units away. Do not silently map it to
the nearest object or drop it. World-space actor coordinates may reflect movement
between pickup and the next one-second sample. Template instances and transforms
also require care.

Detailed results: ignored notes/analysis/observed_superbrick_candidates.csv and
superbrick_log_spatial_candidates.json. They retain both actor coordinates and
candidate source coordinates. Monitor metadata still has six existing labels;
this review does not promote spatial candidates into verified names/AP locations.

Examples:
- 960 -> WI_Forest_0603 j_pup, 0.341 units (second candidate 9.878).
- 6752 -> SF_Residential_0822 P_pup2, 0.393 units.
- 683 -> WI_Forest_0902 CAFE_SBRICK_01_PU, 0.386 units.
- 680 -> WI_Forest_0902 CAFE_CRABNET_01_PU, 0.648 units.

The observations support useful local clusters, not one global arithmetic rule:
WI_Forest_0701 source indices 3/5/6 match bits 361/363/364 (base 358). In
WI_Forest_0902, source indices 0/1 match 680/681 while 3/4/5 match 682/683/684;
using one raw-index base would mislabel part of that resource. Resolve source
registration/packing before extrapolating to uncollected objects.

Next improvements: preserve stable scene/process identity on observations,
capture pre-pickup/current actor samples and native pickup instance identity,
and verify packing across small/large/template-generated objects. Existing
coordinates are already saved; more user walking alone does not solve ID packing.

Follow-up user_monitor_new_city_observations.json adds four pickup events in
WI_Forest_0702: bits 667,665,664,666, all with actor coordinates. Candidate output
files above were refreshed from the cumulative log; they now contain 22 events.
An additional character discovery at 05:50:08 records NPC_CitizenMale07 model 387,
found=true, owned=0. Its localized display name remains unconfirmed. No additional
city completion flag is recorded in the 64 newly added records. A DetectiveMode
marker also changes; shared movement contexts are not additional AP checks.
