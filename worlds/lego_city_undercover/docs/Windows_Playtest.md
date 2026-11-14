# Windows playtest after this update

Use a new seed for the new item pool and goal. Keep the old game slot; do not delete it. Install **one** APWorld filename and generate with LCU_Chronological_Test.yaml. Existing seeds keep their old item lists and token goal. The GUI starter remains StartLCUNativeClient.cmd.

1. Close the game and client once if a different detective-hook DLL has previously been used. Keep a copy of the Steam save directory. The client also creates a bound-save backup before native delivery.
2. Generate a fresh seed from the included YAML. Host that seed and enter its address/port/slot/password in the GUI. Start the client from the game's main menu if desired; N0CUT5 still applies before loading a save.
3. Load a new game slot. Confirm no checks are sent from another seed's bound slot. On an intentionally reused same-slot save, old completed checks are still supposed to reconcile.
4. Obtain an opening check and verify its own/remote notification. Receive Police and both scan items through their opening checks. Verify an unreceived Detective Scan cannot start; after receiving it, step out of and back into the aura and retry. Test the original criminal scan independently.
5. Receive the first Progressive Astronaut: the notification must name Astronaut and the class must be selectable. Jetpack must remain unavailable. Receive the second: notification must name Jetpack; verify flight. Reconnect/reload: neither stage may change or be granted twice. Further copies do not grant money.
6. Receive a class-specific skin before its class. It should be held rather than unlock that profession. Receive the class and verify the skin is then selectable without purchase. Civilian special categories such as Deep Sea Diver should not wait for Police.
7. At a mission, collect a character token, each shield quarter, a Red Brick, reach Hero and finish. Compare monitor and AP location IDs. For Blackwell test both assignments independently. Whole-shield mode should send one shield location after all four parts; quarter mode sends four.
8. Test grant/removal of a clearly observable cheat in the GUI. Confirm discovery, owned, Extras-active and save proof are separate. Manually enable its effect in Extras. A received ownership item alone need not turn the effect on.
9. While driving, pick up a check and receive a package. Confirm check reporting stays independent of native grant eligibility. Stop safely and verify pending save/ownership status and popup behavior.
10. Disconnect AP, complete a check, reconnect. It must be reported once. Restart the client and game; saved currency must not be credited again. Switch to a differently bound slot; checks/goals/native writes must stop with the binding error.
11. Finish the final assignment to test the default goal. For all_assignments, verify all 15 named descriptor completions are required. Token receipts alone must not goal these new seeds.

Known limits: full city traversal logic and native ticket/district gates are unfinished. The open_world option changes AP order only. Do not use it expecting a postgame native world. This procedure is targeted validation, not a claim that the fresh story can already be completed without discovering missing logic.

Attach the GUI log export, exact seed, game slot, location IDs and the first failed step when a discrepancy occurs. Test grants remain local test overrides; they are not AP receipts.
