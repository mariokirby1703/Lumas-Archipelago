# Experimental LEGO City Undercover setup

Use the supported Steam/Windows DX11 build. Install the experimental APWorld for generation, prepare a YAML with Archipelago's template generation, generate/host the seed and connect the source client. The existing monitor EXE is a separate read-only diagnostic tool.

From this checkout, use tools/start_native_client.py --connect HOST:PORT --name SLOT. It enables native items and the cutscene permission option. The local build/lego_city_undercover/StartLCUNativeClient.cmd asks for the server and uses slot Luma. Direct Client.py also supports --enable-native-items; leaving that flag off records receipts without native effects.

Build LCUItemBridge.dll with tools/build_item_bridge.py when developing; ziglang is only a build dependency. The native starter uses the repository Python environment and forwards server input as subprocess arguments without a shell.

Before mutation, the client finds one Steam save matching the loaded character bank, binds the exact file to the AP journal and backs up the slot. If matching is ambiguous, supply --native-save-file PATH/gameN.legocityundercoversavegamedata for the loaded slot. Changing native slots while connected is unsupported; the journal refuses a different file. Use one native client per game process.

Native delivery handles model ownership without purchase/discovery, bound abilities, cheat ownership and the requested currency packages. It requests autosave immediately after a grant; the game controls when it can complete. The client verifies actual serialized model/ability/cheat values and currency receipt markers before marking a receipt applied. Restoring an older native save triggers reconciliation again. Currency markers bind the native save to one AP seed/slot and prevent duplicate credit after retries and lost responses.

Native reward suppression follows seed category options and received entitlements. Checks are durably queued before suppression. Original source discovery stays intact. An unreceived equipped model first switches through the native starting-civilian path. Suppression polls during ordinary gameplay and defers busy interactions; the original popup may still appear.

Character/disguise and pickup detection has multiple live observations. New currency grants, suppression, fallback switching and reload behavior need controlled in-game tests. Symbolic abilities without native bindings remain queued and logged. Story/area entrance gates, object appearance gating, full co-op and open-world initialization are not completed.

Existing compatible seeds work with these client changes. A new seed is needed when changing generation options/pool/locations. The item pool includes useful large brick packages, useful skins, progression disguises/abilities, 40 cheat definitions and weighted Studs/small-brick fillers. Cutscene permission still also requires the seed's cutscene_skip option.

See [native delivery status](research/native_item_delivery_status.md) for exact bindings and evidence. Do not treat a journaled receipt, a save request or an untested effect as a completed live validation.
