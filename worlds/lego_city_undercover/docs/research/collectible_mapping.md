# Collectible mapping

Static candidates, not runtime-detectable AP checks.
No persistent completion offsets, ability requirements, or district display-name mappings are verified.

| Source table | Definitions | Evidence |
|---|---:|---|
| `stuff/sidemissions/parkourinfo.txt` | 19 | SHA-256 `795d929c0ddde4338837f3365e4c65e642bb5e8e5250cfa1463d46b6e83b5895` |
| `stuff/sidemissions/timetrialsinfo.txt` | 60 | SHA-256 `f86638630a3fcd30373c6c0465efa09e9b6178c548f4108a87bedcbc028de3f2` |
| `stuff/sidemissions/vehicletheftinfo.txt` | 13 | SHA-256 `f3501aac47b53c2f006c5c2b2f89082e5419df62784e54c9b9abafda36b529c6` |

TimeTrials contains 60 definitions; this does not establish 60 active, independent checks.
VehicleTheft entries use Type=Time Trial; category must preserve the source table.
Full internal names and rewards remain in ignored notes/analysis/candidate_missions.json.
The scanner table separately defines four shield-piece pickup types; persistence is unverified.

Scanner objective table: 1059 rows, SHA-256 `6adcb0bf3d6f90b150b4ce7875a0f341d4732c11daede71a1b47cf0c51c65a10`.
Declared scanner locks are candidate requirements, not a complete reachability proof.

| Internal objective type | Rows |
|---|---:|
| `ASTRO_CatchAliens` | 17 |
| `ASTRO_Conquer` | 20 |
| `CONSTRUCT_Brew` | 20 |
| `CONSTRUCT_Drill` | 17 |
| `COP_AudioScan` | 16 |
| `COP_CriminalScan` | 12 |
| `CSwap_BLUE` | 1 |
| `CSwap_BROWN` | 2 |
| `CSwap_GOLD` | 1 |
| `CSwap_GREEN` | 1 |
| `CSwap_ORANGE` | 1 |
| `CSwap_PINK` | 1 |
| `CSwap_PURPLE` | 1 |
| `CSwap_RED` | 1 |
| `CSwap_SILVER` | 1 |
| `CSwap_YELLOW` | 1 |
| `Clue` | 658 |
| `DisguiseBooth` | 17 |
| `FARMER_Flowers` | 20 |
| `FARMER_Pigs` | 22 |
| `FARMER_Pigs_FLOW` | 3 |
| `FIREMAN_BBQ` | 17 |
| `FIREMAN_Cats` | 17 |
| `MINER_BoulderSmash` | 22 |
| `MINER_StatueSmash` | 17 |
| `ParkourChallenge` | 19 |
| `ROBBER_ATMSmash` | 18 |
| `ROBBER_CarTheft` | 13 |
| `Race` | 17 |
| `SuperBuild` | 65 |
| `SuperBuild_Level` | 7 |
| `TicketMachine` | 14 |

| Internal district | Rows |
|---|---:|
| `BR_Brooklyn_Bridge` | 5 |
| `BR_Golden_Gate` | 4 |
| `BR_Twin_Bridge` | 2 |
| `IS_Liberty_Island` | 15 |
| `IS_Prison_Island` | 15 |
| `IS_Space_Centre` | 23 |
| `NY_Airport` | 26 |
| `NY_Beach` | 26 |
| `NY_Canal` | 2 |
| `NY_Central_Park` | 16 |
| `NY_Chinatown` | 23 |
| `NY_Downtown` | 22 |
| `NY_Downtown_East` | 22 |
| `NY_Downtown_West` | 20 |
| `NY_Little_Italy` | 23 |
| `NY_Times_Square` | 20 |
| `NY_Uptown` | 17 |
| `SF_Docks` | 26 |
| `SF_Residential` | 25 |
| `WI_Farmlands` | 22 |
| `WI_Forest` | 25 |
| `unspecified` | 680 |

## Optional Super Brick pickup research

The user proposed rainbow Super Bricks as optional locations. A pre-pickup snapshot is recorded as
live_rainbow_superbrick_before_pickup.json; the reported possible 5,000 reward is not yet verified.
A currency increase alone does not uniquely identify a pickup. Inclusion requires a stable per-object
identifier or completion condition, plus verified persistence/respawn behavior and first-collection handling.
No Super Brick locations or IDs have been registered yet.

The small rainbow Super Brick was then collected. The user reported +1,000; the before/after snapshots
are live_rainbow_superbrick_before_pickup.json and live_rainbow_superbrick_after_pickup.json.
This verifies a reward comparison, not yet a stable individual pickup flag or respawn behavior.

User-reported Super Brick geography: the first +1,000 pickup was in an Auburn backyard beside two
large tank-like structures. Two further pickups are visible on an adjacent factory-like rooftop.
These are descriptive research labels; no coordinates, official names or stable object IDs are confirmed.

The two adjacent rooftop pickups were collected separately: currency 5,462->6,462->7,462,
each +1,000, with no change in the decoded city-objective table. Before/intermediate/after snapshots
are preserved under live_two_superbricks_*.json. These samples do not yet expose individual pickup IDs.

## Cherry Tree Hills station gumball-machine construction

The user built four of five machines. At 2/5, CityObjective bits 524 and 526
were newly set relative to the icebox snapshot; their individual order is unknown.
The isolated 2/5 -> 3/5 step set bit 527 (hash 1479167923), and 3/5 -> 4/5
set bit 525 (hash 903247860). Gold Brick count stayed at 2 on those isolated steps.
Snapshots and comparisons are live_station_gumball_* under notes/analysis.

The fifth machine is currently inaccessible. The user reports that the station
entrance must be blasted open with dynamite, requiring the miner disguise.
This is an access-route requirement for the remaining machine, not evidence that
building gumball machines itself requires miner. Alternate routes, the fifth
instance flag, completion reward and eventual AP item granularity remain unverified.

## Playground construction group

The first user-reported playground build displayed 1/5. Relative to the station
4/5 snapshot, bit 486 (hash 132643829) became complete; Gold Bricks remained 2.
The user explicitly confirmed miner/dynamite is required for the last playground
object as well. The exact obstacle, remaining instance identities and alternate
routes have not been verified. Evidence: live_playground_build_1of5* snapshots.

## Optional basketball location research

The user scored once, then reported three consecutive successful baskets, a Steam
achievement and Chase cheering. The executable contains `BASKETBALL_3_OUT_OF_3`,
`BasketBallAddOn`, and win/fail animation names. Residential GIZ resources contain
`MG_Basketball_CMPLX` instances. These support investigating a three-consecutive-hit
completion condition; they do not establish a persistent per-hoop flag.

No decoded CityObjective flags changed after either observed stage. Studs, bricks
and Gold Bricks were unchanged between the one-hit and three-hit snapshots.
Evidence: live_basketball_before.json, live_basketball_after_hit.json,
live_basketball_three_hits.json and their observation reports. A global Steam
achievement cannot uniquely identify multiple hoops or provide seed-scoped replay
state. Optional per-hoop checks need local completion detection and per-slot AP
persistence; neither is implemented yet.
