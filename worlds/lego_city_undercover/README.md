# LEGO City Undercover experimental APWorld

Current pass (2026-11-21): [completion report](docs/research/reliability/completion_report_2026_11_21.md). 174/471 exact city pickup bindings, 65 persistent city Superbuild job bindings, native profile/seed grant guards and 1,421 read-only Sheet design rows. 405 test executions (7 skipped) and 180/180 fill simulations; vehicle/creature gameplay validation and destination/story/open-world gates remain incomplete.

Latest follow-up: [pickup proof review and writer guard](docs/research/reliability/pickup_binding_review.md), with 386 passing test executions. Shared binding coverage remains 40/471 until new native observations are available.

Latest pass: [native reliability completion report](docs/research/reliability/completion_report.md) and [remaining TODOs](docs/research/reliability/TODO.md). Version **0.0.1** is intentional. The latest build has 374 passing test executions; new native movement still needs live validation. Use LCU_Chronological_Reliability_Test.yaml for the normal no-area-gate test profile.

Update (2026-11-15): four two-stage progressive class/tool families, independent Police-dependent scans, mandatory early SuperBuild/Detective Scan safeguards, 40 exact city pickup bindings and an opt-in near-boundary area-return prototype. See the [current development report](docs/research/next_major_pass_2026_11_15.md) for validation and remaining limits. Area return has synthetic tests, not a live movement confirmation.

Current status (2026-11-14): new seeds use native final-assignment completion, Progressive Astronaut and source-based district/assignment/section regions. Class-specific cosmetic skins can wait for their base class. Normal pools exclude unbound symbolic effects. Existing receipt IDs and legacy token-goal seeds remain supported.

See the [implementation audit](docs/research/implementation_audit.md), [feature matrix](docs/research/feature_matrix.csv), and [Windows playtest](docs/Windows_Playtest.md). Install only one of the two equivalent APWorld filenames.

Experimental Steam/Windows DX11 integration for Archipelago 0.6.8. The source client detects city and mission checks and can apply native AP items with explicit opt-in. Story/area entrance gates, open-world initialization and complete access logic remain unfinished.

Native delivery now includes character/disguise/vehicle ownership, bound abilities, Red Brick cheat ownership, Studs packages and building-brick packages. AP models do not require purchasing and do not consume their original world token. The user confirmed Magician selection after the booth navigation correction. Currency and reward suppression are built and await their first live effect tests.

The client requests native autosave after grants and verifies models, abilities, cheat ownership and currency receipt markers in the actual save file. A receipt is not marked applied merely because it arrived or a DLL call returned. Currency markers prevent repeat credits after reconnect, lost responses and older-save recovery. A bound slot backup is created automatically before the first mutation.

With native items enabled, check detection and durable queuing precede suppression of unreceived vanilla model/tool/cheat rewards. Equipped locked models first use the native switch to the starting civilian. This is a polling implementation that waits for ordinary gameplay, not an instantaneous interception of every reward animation. Discovery, objectives, source flags and ordinary resource pickups are retained.

## Start and build

Current artifacts:

- build/lego_city_undercover/lego_city_undercover.apworld (experimental filename is an equivalent compatibility package)
- Versioned DLL selected and verified by build/lego_city_undercover/native_items_build.json
- build/lego_city_undercover/StartLCUNativeClient.cmd (local Luma test starter)

From the repository root:

```
.venv/Scripts/python.exe worlds/lego_city_undercover/tools/start_native_client.py --connect HOST:PORT --name SLOT
```

The starter enables native items and the existing N0CUT5 permission option. Without arguments it asks for server and slot. The current native save is automatically identified when exactly one Steam save matches; otherwise use --native-save-file with the loaded slot's gameN.legocityundercoversavegamedata. Keep that native slot bound to the AP seed. Close the prior source client before starting another native client.

To rebuild the DLL (ziglang is required only for building):

```
.venv/Scripts/python.exe worlds/lego_city_undercover/tools/build_item_bridge.py
```

Direct Client.py use remains read-only for items unless --enable-native-items is supplied. The existing monitor EXE is a separate read-only diagnostic tool. A standalone native networking EXE is not provided.

These delivery changes work with an existing compatible seed. Regeneration is needed only to change the generated item pool, options or available locations. Generate YAML through Archipelago's template generation; the user's existing Luma.yaml is unchanged.

## Item pool and coverage

The requested default pool contains 20 useful Super Bricks 1,000 packages and 5 useful Super Bricks 10,000 packages, configurable with super_brick_1000_count / super_brick_10000_count. Character skins are useful; primary disguises/abilities are progression. There are 40 native cheat definitions. Filler includes Studs 1,000 / 10,000 / rare 100,000 and Super Bricks 100 / 250, weighted 80 / 18 / 1 / 30 / 15.

Native bindings do not yet cover every symbolic ability. Carry Objects, Climbing, Crowbar, Fishing, Stethoscope and Rex Fury currently remain queued with explicit unbound-effect logging. Bound Scanner, SuperBuild and other native tools use the actual ability system.

Supported offline progress is reconciled with the AP server and outgoing checks persist until acknowledged. Character token collection differs from ownership; purchasing or equipping creates no token check. Mission checks include completion, shields/quarters, Hero, red bricks, bound pickups and the researched native superbuild path. Ambiguous pickup identities remain excluded. include_unverified opts into additional candidates that are not all proven independent checks.

Locations use source-based regions and known class/tool locks. This does not establish that native gameplay can reach them with the generated item placement. The default goal is native final-assignment completion; City Completion Tokens are a legacy/debug option.

See the current audit and test artifacts for validation counts. Historical [native delivery status](docs/research/native_item_delivery_status.md) records earlier implementation evidence and exact persistence bindings; its older test/logic summaries are superseded by the audit.

Research assets and gamefiles stay in ignored notes/. They are not packaged into the APWorld.

Currency backlog optimization: up to 24 ordered packages are credited in one native command, with one combined autosave. The native watermark skips previously credited indices before summing amounts; both balances and the final receipt marker are updated before requesting save.
