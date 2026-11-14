# LEGO City Undercover experimental APWorld

Experimental Steam/Windows DX11 integration for Archipelago 0.6.8. The source client detects city and mission checks and can apply native AP items with explicit opt-in. Story/area entrance gates, open-world initialization and complete access logic remain unfinished.

Native delivery now includes character/disguise/vehicle ownership, bound abilities, Red Brick cheat ownership, Studs packages and building-brick packages. AP models do not require purchasing and do not consume their original world token. The user confirmed Magician selection after the booth navigation correction. Currency and reward suppression are built and await their first live effect tests.

The client requests native autosave after grants and verifies models, abilities, cheat ownership and currency receipt markers in the actual save file. A receipt is not marked applied merely because it arrived or a DLL call returned. Currency markers prevent repeat credits after reconnect, lost responses and older-save recovery. A bound slot backup is created automatically before the first mutation.

With native items enabled, check detection and durable queuing precede suppression of unreceived vanilla model/tool/cheat rewards. Equipped locked models first use the native switch to the starting civilian. This is a polling implementation that waits for ordinary gameplay, not an instantaneous interception of every reward animation. Discovery, objectives, source flags and ordinary resource pickups are retained.

## Start and build

Current artifacts:

- build/lego_city_undercover/lego_city_undercover_experimental.apworld
- build/lego_city_undercover/LCUItemBridge.dll
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

All generated locations are connected in the experimental region graph. This does not establish that native gameplay can reach them with the generated item placement. The current goal is receipt of City Completion Tokens.

131 tests pass. The latest read-only native preview preserved inventory/ability bytes and verified all 51 serialized ability bits against the running game. See [native delivery status](docs/research/native_item_delivery_status.md) for implementation evidence, live test boundaries and exact persistence bindings.

Research assets and gamefiles stay in ignored notes/. They are not packaged into the APWorld.

Currency backlog optimization: up to 24 ordered packages are credited in one native command, with one combined autosave. The native watermark skips previously credited indices before summing amounts; both balances and the final receipt marker are updated before requesting save.
