# Native bridges

The current item bridge is built with:

```
.venv/Scripts/python.exe worlds/lego_city_undercover/tools/build_item_bridge.py
```

It produces build/lego_city_undercover/LCUItemBridge.dll using ziglang. The generated booth_selection_patch.h stays in build/. reward_enforcement.h and purchase_gate.h are source-controlled beside item_bridge.cpp. purchase_gate_patch.h is generated from purchase_gate.py.

The source client enables this DLL only with --enable-native-items. Protocol version 2 is 64 bytes, using Local\LCUItemBridge2_<pid> and a WH_GETMESSAGE hook on the verified game window thread. A separate 320-byte Local\LCURewardPolicy_<pid> mapping supplies bounded entitlement masks. Commands never accept arbitrary function addresses. Opcode 9 previews policy without mutation; opcode 4 is a native availability query. Other opcodes grant models, bound abilities, cheat ownership, currency or request native autosave.

The executable hash, process/thread, indices, names, model count, profile-bank aliases and function prefixes are checked. Grants/suppression require ordinary gameplay; save requests and read-only probes are separate. The DLL is unhooked after each command. The booth navigation changes are self-contained instructions in game memory and disappear on process restart.

See ../../docs/research/native_item_delivery_status.md for current evidence and boundaries. death_bridge.cpp/CMakeLists.txt are the older separate DeathLink experiment and are not the item bridge build path.

Shop guards persist in a game-owned executable page and use AP-managed model masks to reject purchases before wallet changes. Buy UI is hidden for unreceived models. No guard refers to the unloaded DLL. Automatic actor replacement is disabled after an unresolved game crash; equipped unreceived models defer revocation until the player changes outfit manually. A named mutex prevents two updated native clients from running together. These shop changes have synthetic x64 execution coverage and still require live UI verification.

Category availability at 0x26210 also accepts ownership of a character in that subcategory, derived at query time without source discovery writes. A running game can retain an old DLL file mapping; build a parallel filename with --output and record dll_filename in build/lego_city_undercover/native_items_build.json for the source launcher/client. Current build: LCUItemBridgeCategory.dll.

The prior 0x26210 category-notification experiment is superseded: Category2 restores it and patches derived UI eligibility counts at 0x265489 plus the mode-3 label at 0x26f2c3. Both use found OR owned; no inventory source flag is written. Current parallel build is LCUItemBridgeCategory2.dll. Live selection remains pending.
