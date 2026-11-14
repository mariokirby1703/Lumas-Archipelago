# LCU Native GUI: lokale Test- und DLL-Sicherheitskorrekturen

Basierend auf Branch `Lego-City-Undercover-AP`, Commit `a871e86d129a7ba4db2468dd6fcc39cd153c9851` (14.11.2026). Dieses ZIP überschreibt keine persönlichen Save-Dateien und enthält **keine fertige DLL**.

## Installation

1. **LEGO City Undercover und den Native Client schließen.** Die Steam-Saves und den Repo-Stand sichern.
2. ZIP in den Hauptordner von `Lumas-Archipelago` entpacken. Die Pfade beginnen mit `worlds/lego_city_undercover/...`.
3. **Einmal `worlds\lego_city_undercover\tools\RebuildLCUNativeBridge.cmd` ausführen.** Dieser Build ist für den neuen Opcode `17` (lokale Währung) und `18` (lokales Item entfernen) nötig. Die vorhandene alte DLL wird nicht überschrieben, sondern eine neue `LCUItemBridgeTests_<Hash>.dll` erstellt und in `build/lego_city_undercover/native_items_build.json` ausgewählt.
4. Falls `ziglang` fehlt: `.venv\Scripts\python.exe -m pip install ziglang`, danach Schritt 3 wiederholen.
5. `worlds\lego_city_undercover\tools\StartLCUNativeClient.cmd` starten, verbinden und einen **gesicherten Test-Spielstand** verwenden.

## Was die Fehlerprotokolle bedeuten

- `Native command 18 (...) timed out` deutet stark auf eine veraltete oder nicht erreichbare DLL-Hook-Implementierung hin. Das Build-Manifest muss nun zur *aktuellen Quelle und DLL-Datei* passen. Ein echter Timeout kann dennoch andere Ursachen haben, daher auf read-only Spielstatus und Log achten.
- `TEST angefordert` bestätigt nur den GUI-Klick. Neu wird der nächste native Snapshot gegen den erwarteten Owned-/Ability-/Cheat-Zustand geprüft, bevor `TEST BESTÄTIGT (Spiel-RAM)` erscheint.
- `Ability: Police` schaltet das native Polizeimodell frei, **zieht die Verkleidung aber nicht automatisch an**. Prüfe zunächst im Verkleidungsmenü den Besitz und die Auswahl. Ein sofortiger Actor-Swap ist wegen früherer Crashes nicht Teil des Patches.
- `Red Brick Cheat: CHEAT_BOOST` ist ein Cheat-Besitz-Item und kein Red-Brick-Fundort. Für den sichtbaren Effekt kann zusätzlich eine Aktivierung über das Extras-Menü bzw. die passende Spielsituation nötig sein. **Diese ZIP implementiert keine unvalidierten nativen Cheat-Effekt-Toggles.**
- Der Filter `Rote Steine / Cheats` zeigt alle im `catalogue.json` vorhandenen Cheat-Items. Die Spielquellen definieren 40 native Cheat-Einträge (35 benannte Cheats plus 5 Stud-Multiplikatoren), die GUI zeigt sie nun als eigene Kategorie. Nicht jeder rote Stein ist ein eigenständiges Item in der AP-Liste, Fundorte sind Locations.
- `Reader waiting: player is busy or not alive` wird als transienter Zustand behandelt. Fehler wie `Invalid bounded diagnostic read` führen weiterhin zur Neuinitialisierung, statt unsichere Daten zu verwenden.
- Warnungen über andere AP-Worlds ohne `__init__.py` sind unabhängig von diesem LEGO-Spielclient und werden hier bewusst nicht geändert.

## Schutzmechanismen

- Eine ungewisse Native-Aktion nach Timeout wird nicht automatisch erneut ausgeführt. Ein erneuter Versuch benötigt einen neuen ausdrücklichen Klick. Bei Währung wird der Befehl nach ungewisser Ausführung grundsätzlich **nicht** wiederholt.
- Lokale Testvergaben sind weiterhin keine Archipelago-Receipts. AP-Checks und Seedbindung werden durch diese GUI-Tests nicht ersetzt.
- Wenn die DLL nicht nachvollziehbar zur aktuellen Quelle passt, verweigert der GUI-Client native Änderungen, bis die DLL neu erstellt wurde.
- Bestätigte Tests prüfen den Arbeitsspeicher. Dies ist **keine zusätzliche Garantie für eine dauerhafte Speicherschreibbestätigung**.

## Tests

```powershell
.venv\Scripts\python.exe -m unittest worlds.lego_city_undercover.tests.test_native_gui_repair -v
.venv\Scripts\python.exe -m unittest worlds.lego_city_undercover.tests.test_test_overrides -v
.venv\Scripts\python.exe -m unittest worlds.lego_city_undercover.tests.test_native_client_gui -v
```

Diese Tests sind keine Ersatzprüfung für reale Spieltests. Native DLL und Spielzustand müssen auf Windows mit der unterstützten EXE separat geprüft werden.
