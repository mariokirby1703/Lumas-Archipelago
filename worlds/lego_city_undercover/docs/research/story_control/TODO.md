# Remaining story control work

26 November follow-up: all 15 replay identities and receipt-derived entitlement decisions are implemented ([report](assignment_pass_2026_11_26.md)). The two previously absent canonical Blackwell access items now exist. These do not install native admission hooks; every native-menu/activation/gating task below remains open.

This list is explicit unfinished implementation, not a claim that native Open World or a pause-menu chapter selector exists.

## P0: original pause menu and independent chapters

- [ ] Implement the actual native pause-menu entry factory and submenu lifecycle: frontendmain.baml nodes, PauseMenuDrawer ownership, input/controller focus, activation callback and teardown. Root drawer lookup at 0x79377 is NOT an entry-creation API. No external chapter window is a substitute.
- [ ] Implement all 15 chapter activation transactions using original flow transitions. Achievements_MarkChapterStart (0x84f0) records event flags; it does not select/start a chapter. Preserve permanent Flow_Completed, assignment completion, shield/Hero/token states and AP outgoing checks.
- [ ] Establish an isolated per-save chapter model. Achievements complete (0x84b0 -> 0x7cf0) writes LegoAchievements +0x110 / +0x188, but per-save/Steam isolation is not verified. The event reader never queues chapter-completion checks or infers an active chapter.
- [ ] Validate abort/resume/replay and Chapter 6 -> 3 -> 6, then Chapters 12?15, including both mansion assignments and timed/automatic transitions. Do not erase story history or bulk-apply developer presets.

## P0: coherent native Open World initialization

- [ ] Determine a reversible minimal initialization for PDA/map, police HQ, traffic/population, city jobs, bridges/travel, save setup and chapter selection without granting tools or completing story flags. Existing narrowly scoped HQ/SuperBuild fixes remain intact.
- [ ] Native Open World remains unsupported; normal new seeds now reject it. experimental_items retains only explicit AP-graph research compatibility, not a native feature. Existing seeds/IDs are not migrated silently.

## P1: pre-consumption native access and travel

- [ ] Bind chapter/assignment hotspot and invitation eligibility before StartLevel is consumed. Cover normal/replay/summary/automatic/split-screen routes and rearm a denied interaction after receipt. Blocking final Door::Trigger is insufficient.
- [ ] Map legacy Story Access assignment IDs to real native effects before enabling them in ordinary seeds. Do not add ineffective progression tickets.
- [ ] Implement native destination selection checks for train/ferry/map/scripted travel and safe profile-bound reload recovery. Keep the 90 m guard and existing near-boundary/vehicle/creature restrictions until validated.
- [ ] Execute the existing foot/run/jump/car/bike/bus/boat/air/hover/passenger/rail/pig/Behemoth matrix, including physics/controls/save feedback; RPC success is not a gameplay verdict.

## P1: mission constructions and reward evidence

- [ ] Live-test the six newly source-bound non-mine mission builds: exact owner scene, runtime name, native cost, final state and flag; test two matching instances are quarantined rather than guessed.
- [ ] Establish independent native persistence for every mission build. Until then the durable AP queue preserves observed completions only; do not infer construction from mission completion or disappearance.
- [ ] Investigate inactive Fire Extender references and the Scrapyard crane template. A referenced template/disabled script is not an independently collectible Super Build. Do not add locations without a genuine construction event.
- [ ] Paradise Pool/Space Shuttle/Serenity Bridge candidates must be reconciled with the 65 city jobs before adding another story location.
- [ ] Recheck existing story disguise detectors when the class was already AP-owned. Only the scoped COP/PDA recovery has specific earlier evidence; independent source events remain required for the other outfits.

## Per-Sheet-point outstanding work

All 150 Sheet points are in story_point_review.csv. Fourteen source-bound actions are implemented; 35 points reuse existing IDs. Starts/completions remain control events, not automatic extra checks.

| Chapter | Sheet cell | Point | Remaining work |
|---|---|---|---|
| 1 | A2 | Chapter 1 Start | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 1 | A4 | Communicator / Scanner | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 1 | A5 | Detective Scan | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 1 | A6 | Navigation | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 1 | A8 | Criminal Scan | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 1 | A10 | Steal the Sandwich back | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 1 | A12 | Chapter 1 Complete | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 2 | B2 | Chapter 2 Start | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 2 | B4 | Repair the Gas Station Pumps | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 2 | B6 | Superbuild | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 2 | B8 | Arrive at Jenny's Diner | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 2 | B9 | Special Assignment #1 Start: Some Assaults | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 2 | B11 | Parkour | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 2 | B12 | Chapter 2 Complete | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 3 | C2 | Chapter 3 Start | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 3 | C3 | Data Scan | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 3 | C5 | Open the Gate into Prison | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 3 | C6 | Fetch the Prisoners Basketball | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 3 | C7 | Special Assignment #2 Start: Trouble in Stir | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 3 | C10 | Train Travel | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 3 | C11 | Sound the Steam Whistle to end the Miners Shift | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 3 | C12 | Special Assignment #3 Start: Miner Altercation | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 3 | C16 | Chapter 3 Complete | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 4 | D2 | Chapter 4 Start | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 4 | D3 | Build Serenity Bridge | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 4 | D4 | Special Assignment #4 Start: Kung Fool | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 4 | D6 | Advanced Combat | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 4 | D8 | Beat up the Robbers at Crabby Cove's Dock | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 4 | D9 | Bring the Police Truck to the Police Station | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 4 | D10 | Chapter 4 Complete | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 5 | E2 | Chapter 5 Start | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 5 | E3 | Chase Undercover Outfit | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 5 | E4 | Audio Scan | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 5 | E5 | Reach the Parking Lot at the Art Gallery | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 5 | E6 | Stop Bucky Butler | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 5 | E7 | Pick up Forrest Blackwell | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 5 | E8 | Bring Forrest Blackwell to the Theater | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 5 | E9 | Grill Chicken Wings at the Pool in Paradise Sands | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 5 | E10 | DJ at the Pool in Paradise Sands | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 5 | E12 | Chase the Burglar at Chan's Limo Place | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 5 | E13 | Chapter 5 Complete | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 6 | F2 | Chapter 6 Start | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 6 | F3 | Construct the Police Chaser Bike | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 6 | F4 | Time Trials | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 6 | F5 | Take Moe De Luca to the Hideout | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 6 | F7 | Special Assignment #5 Start: Dirty Work | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 6 | F8 | Color Gun | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 6 | F12 | Camera / Photography | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 6 | F14 | Chapter 6 Complete | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 7 | G2 | Chapter 7 Start | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 7 | G3 | Boat Commandeering | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 7 | G4 | Reach Apollo Island | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 7 | G5 | Special Assignment #6 Start: Astronaughty | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 7 | G9 | Chapter 7 Complete | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 8 | H2 | Chapter 8 Start | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 8 | H3 | Save Forrest Blackwell from his Abductors | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 8 | H5 | Special Assignment #7 Start: Scrapyard Scrap | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 8 | H8 | Chapter 8 Complete | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 9 | I2 | Chapter 9 Start | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 9 | I3 | Reach Duke Huckleberry's Office | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 9 | I4 | Ride the Horse to Farmer Hayes Farm | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 9 | I6 | Escaped Pig #1 | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 9 | I7 | Escaped Pig #2 | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 9 | I8 | Escaped Pig #3 | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 9 | I9 | Chapter 9 Complete | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 10 | J2 | Chapter 10 Start | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 10 | J3 | Reach the Museum | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 10 | J4 | Special Assignment #8 Start: The Colossal Fossil Hustle | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 10 | J9 | Special Assignment #9 Start: Hot Property | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 10 | J12 | Reach the Hospital | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 10 | J14 | Helicopter Access | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 10 | J16 | Chapter 10 Complete | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 11 | K2 | Chapter 11 Start | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 11 | K3 | Crash Mats + New Super Builds (Helicopter Platforms) | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 11 | K4 | Meet up with Moe De Luca | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 11 | K5 | Build the Paradise Pool | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 11 | K6 | Listen to Vinnie's Argument with Rex Fury | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 11 | K7 | Special Assignment #10 Start: Smash 'n' Grab | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 11 | K9 | Escape and fight the Sentinels | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 11 | K10 | Special Assignment #11 Start: They All Scream for Ice Cream | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 11 | K12 | Chapter 11 Complete | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 12 | L2 | Chapter 12 Start | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 12 | L3 | Special Assignment #12 Start: High Steal | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 12 | L7 | Reach the Observatory | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 12 | L9 | Chapter 12 Complete | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 13 | M2 | Chapter 13 Start (automatic after Chapter 12) | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 13 | M3 | Special Assignment #13 Start: Disruptive Behavior | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 13 | M4 | Jetpack | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 13 | M6 | Fly to Blackwell's Mansion | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 13 | M7 | Special Assignment #14 Start: Breaking and Reentering | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 13 | M9 | Chapter 13 Complete | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 14 | N2 | Chapter 14 Start (automatic, timed in vanilla) | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 14 | N4 | Take the Shield Prototypes to Blackwell Tower | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 14 | N6 | Chapter 14 Complete | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 15 | O2 | Chapter 15 Start | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 15 | O4 | Special Assignment #15 Start: Fly Me to the Moon | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| 15 | O5 | Defeat T-Rex Fury | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 15 | O6 | Defeat Rex Fury | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 15 | O7 | Land safely on Earth | Resolve a source-specific event or completion flag; AP ownership and current chapter stage are not collection evidence |
| 15 | O9 | Chapter 15 Complete (Goal) | Implement original chapter/mission entry control; never generate an automatic duplicate check |
| Post Game | P2 | Brick Multiplier x2 | Implement original chapter/mission entry control; never generate an automatic duplicate check |
