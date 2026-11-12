# Setup status

No installable randomizer is available yet. There is no lego_city_undercover.apworld,
LegoCityUndercoverAPClient.exe or playable YAML in this revision.
Do not install the research directory as a finished world or generate seeds against placeholder data.

For developers, follow development.md to reproduce analysis using your own Steam files under notes/gamefiles.
For the read-only connection diagnostic, start the installed Steam game and run bridge/diagnose.py with 64-bit Python.
No DLL installation is required. No save files are edited, backed up or restored automatically.

If game_not_running appears, finish Steam prerequisites and confirm LEGOLCUR_DX11.exe is actually running.
For unknown_executable, compare its full hash to the recorded inventory; no gameplay profile supports that version.
For diagnostic_failed, inspect the reported Win32 error and run under the same user as the game.
No privilege elevation or disabled security setting is required by the diagnostic.

A standalone diagnostic archive is now available at `build/lego_city_undercover/LegoCityUndercoverDiagnostics.pyz`.
Run from the repository root:

```powershell
python build/lego_city_undercover/LegoCityUndercoverDiagnostics.pyz --research-state --objectives --inventory --actor --story
```

It requires 64-bit Python 3.11+; it is a read-only research tool, not an Archipelago client.
In this development environment the normal sandbox denied process access; the same-user read succeeded
when executed outside that sandbox. This is separate from Windows administrator rights.
Keep --objectives output marked experimental until actual completion transitions have been compared.

--inventory reads current Studs, Super Bricks, the Gold Brick counter and experimental character inventory.
Stud/Super Brick changes and the current three-outfit roster have now been compared live. Pending unlocks are
reported separately from found bits and owned bytes; these are not interchangeable AP checks yet.

--actor reads the equipped model, attached-object names and current context. --story reads selected named
Job values. Chief-office key presence, COP model and Default context were read live while paused.
Key consumption, actual hand-held state and detective context transitions are not yet verified.
