# Police station gold-brick inventory

All extracted police_station .giz resources contain ten type-71 reward pickups.
There are seven remaining sources beyond the live-tested toy vehicle, line-up room
and popcorn. Static resource coordinates and stable source keys are exported to
notes/analysis/police_station_gold_bricks/catalogue.json and locations.csv.

| Room | Pickup | Source / associated action | Scanner requirement |
| --- | --- | --- | --- |
| Lobby | GB_RideOn | Toy police vehicle ride, already live tested | none declared |
| Lobby | GB_Portraits | Four portrait objects / Portrait_Spellit_01,02,03,05 | none declared |
| Lobby | GB_FilingCabinet | Silver_FilingCabinet, exp_Dynamite_02, LCPD_Lobby_Dynamite | miner |
| Briefing room | GB_Popcorn | Eat popcorn, already live tested | none declared |
| Briefing room | GB_Donut | Donut reward; DonutTable_Buildit and Supercarry_Donut_Table_item also exist | robber |
| Basement / garage | GB_GoldBrickShop | Reward at gold-brick shop, LCPD_BM_GB_GBShop | construction |
| Basement / garage | GB_RedBrickShop | Reward at red-brick shop, LCPD_BM_GB_RBShop | robber |
| Basement / garage | GB_VehShop | Reward at vehicle shop, LCPD_BM_GB_VehShop | Parkour ability |
| Basement / garage | GB_FireDoor | Fire door; explicit PDAScan_LockPickup in hub_propcontrol_garage.sf | fireman |
| Line-up room | GB_LineUp | Hidden brick, already live tested | none declared |

Scanner requirements come directly from GAME7/stuff/scanner/scanner_objectives.txt
around lines 5273-5367. These are class/ability annotations, not a complete AP access
rule: more granular tools such as the separate Fire Axe may still be required.
No tool requirement is invented from a shop name. Four portraits correspond to
four scanner clues but one GB_Portraits reward; they are not four independent
gold-brick checks. Exact gameplay actions for the seven remaining sources are not
yet fully live verified.

All ten are now registered under city_activities using their own collected
reward-object state, without interpreting the global gold total as a location.
The seven new registrations are labelled static_activity_reward, not live verified.
Their associated raw clue entries are removed to avoid duplicate checks. Persistent
objective completion is used only where separately verified (currently popcorn).
Existing source IDs are retained. Current seeds without these locations cannot
gain extra randomized locations; new seeds include them when city_activities is on.

Reproduce with tools/research_station_gold_bricks.py. --register updates only local
catalogue/reader metadata; it performs no game or save writes. The catalogue builder
also preserves the static-versus-live status and scanner lock metadata. Five reader
tests and thirteen generation tests passed after registration.
