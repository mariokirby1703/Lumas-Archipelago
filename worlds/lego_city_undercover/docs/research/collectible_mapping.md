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
