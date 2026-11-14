# Hidden gold brick in the station line-up room

User reported collecting a gold brick in a station room. The read-only snapshot
build/lego_city_undercover/station_gold_brick_observation.json shows GB_LineUp,
native type 11, native_collected=true in Police_Station_Line_Up_Room; four gold
bricks total were visible in native stats. The object name, local coordinates
(0.170628, 0.159998, 0.080279) and unique static type-71 source match:

GAME7/levels/standalones/police_station/police_station_line_up_room/police_station_line_up_room.giz:27:1

The existing catalogue ID 1297348804 is retained. This source was previously an
unverified pickup and absent from the user's current seed. It is now named
Police Station: Line-Up Room Hidden Gold Brick, under city_activities, with exact
scene/name/type/collected-state detection in activity_rewards.json. It is not
inferred from the aggregate gold-brick count and does not invent an activity that
the user has not described. Snapshot matching confirms the new reader recognizes it.

The running seed cannot gain a new location retrospectively. No replacement or
unrelated check was sent. New seeds include this location when city_activities is
enabled. Four activity tests and thirteen generation tests passed after the change.

## Briefing-room popcorn

The following live snapshot, station_popcorn_observation.json, shows GB_Popcorn
collected in Police_Station_BriefingRoom and five gold bricks total. Compared with
the preceding snapshot, LCPD_BR_PopCorn (hash 753712927, completion bit 716) also
became complete. The unique static source is
police_station_briefingroom.giz:735:42 at local (3.034476, 0.302079, 1.305344).

Location 1627984646 is now named Police Station Briefing Room: Eat Popcorn under
city_activities. It accepts that specific persistent action-completion objective
or its exact collected reward object, so leaving the room does not lose the check.
The raw clue objective is removed from future catalogues to avoid duplicate checks.
The current seed has no matching location; no substitute check was sent.
Five activity tests and thirteen generation tests passed after this addition.
GB_Donut was also observed in the same room, but uncollected; no completion or
specific donut action has been inferred from that observation.
