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

For the 15 November build, generate a fresh seed using LCU_Chronological_Test.yaml. Give each progressive family twice: Police then Grapple Gun; Robber then Color Gun; Firefighter then Fire Axe; Astronaut then Jetpack. Receive Detective Scan or Criminal Scan before Police and confirm it waits; after Police stage 1, confirm the received scan works without granting Grapple Gun. The third clown requires Detective Scan, and the gas-station call-in requires SuperBuild.

Use LCU_Area_Rollback_Test.yaml separately for boundary tests. Begin in Auburn, approach Cherry Tree Hills slowly on foot without its pass, and inspect the copied area diagnostics. Repeat with a supported ground vehicle only after the foot test succeeds. Then receive the pass and confirm entry is allowed. Avoid using fast travel as the first test: distant returns and reload recovery are not supported. No live movement confirmation exists yet.

Known limits: full city traversal logic and native story gates are unfinished; district return is an experimental nearby-boundary prototype. Open-world initialization is unavailable and cannot be combined with area restrictions. This procedure is targeted validation, not a claim that the fresh story can already be completed without discovering missing logic.

Attach the GUI log export, exact seed, game slot, location IDs and the first failed step when a discrepancy occurs. Test grants remain local test overrides; they are not AP receipts.
