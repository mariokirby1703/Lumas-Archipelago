# Post-SA1 user monitor log

Evidence preserved in notes/analysis/user_monitor_post_sa1_log.json and review JSON.
The supplied log has 141 records: 132 context changes, two story headings, one
manual completion annotation, one area heading, one CityObjective, one ability and
three pickup events. No game writes were performed to analyze it.

DataScanner changed false -> true at 18:54:44, existing=1/pending=0, sampled native
tile SF_Residential_0823. This is distinct from Scanner and is independently
observable. The manual Mission abgeschlossen record and story cursor 7 -> 8 are
preserved, but no independent assignment-completion save bit is established.

| New pickup bit | Nearest source in sf_residential_0822.giz | Source index | Distance |
|---|---|---:|---:|
| 6757 | P_pup1 | 22 | 0.300 |
| 6756 | Brick3 | 20 | 0.411 |
| 6753 | Brick2 | 17 | 0.318 |

These are spatial candidate associations, not verified native index decoding.
The latter two fit bit = source index + 6736, but the first would require +6735.
This disproves blindly applying one raw-record-index offset to every source in
this resource based on these spatial matches. Either native indexing differs or
one association needs refinement. Do not insert all three into verified labels or
generalize the previously tested Farmlands offset to this resource.

Pickup event snapshots can precede the reward counter update: 6757's sampled brick
total is 6112; the next event shows 7112; the final event shows 17112. Therefore
do not assign reward size solely from the same polling sample as the new bit.

New useful context observations include Grapple (134), GrappleRope (217), Hang
(136), PoleClimbContext (56), Ladder (164), RideObject (157), and BouncePadJump
(246). Existence of BouncePadJump does not retroactively identify the earlier
mushroom tests or prove its applicability to every trampoline. No action gate is
implemented by observing a context.

City flag SF_RD_0822_Bin_Buildits, hash 1202895009, bit 687, changed false -> true.
Its metadata type is Clue: it remains a puzzle-progress observation, not an extra
AP location. Player position at observation is not necessarily its source position.
