# Known issues

The randomizer is incomplete: no gameplay bridge, AP networking, grants, checks, gating, notifications or release artifacts.
The first Steam launch spent time in RunningInstallScript, then launched successfully.
Process-memory reads require execution outside the sandbox in this environment. No gameplay transition was tested.
No save existed in the inspected conventional userdata path, so save comparison was unavailable.
Two archive entries have no CRC-associated name and are deliberately excluded from named extraction.
Unknown archive variants/compression fail explicitly. Independent QuickBMS output comparison remains outstanding.
Mission/debug tables may contain unused definitions. Scanner locks alone are insufficient for safe progression logic.
An engine action candidate takes a script context; direct calling with guessed arguments can crash or corrupt state.
The research code does not call those methods or write game memory.

Resolved in the read-only diagnostic: current Stud and Super Brick balances are now read and matched against
a controlled live change; three current primary outfit candidates are recognized through bank and pending states.
The wider roster, token/purchase semantics and equipped-character detection still require tests.
