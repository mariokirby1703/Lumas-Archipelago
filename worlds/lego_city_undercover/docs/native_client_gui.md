# LEGO City Undercover: Native Archipelago Client GUI

**Basis:** Branch `Lego-City-Undercover-AP`, Commit `3822c3ffd6091ca2296ae0e49d9fa73336954bef` vom 14.11.2026.

## Installation

1. Archipelago und LEGO City Undercover schließen. **Den aktuellen Repository-Stand und deine Steam-Saves sichern.**
2. Die ZIP-Datei **im Root von `Lumas-Archipelago`** entpacken. Vorhandene Dateien ersetzen. Die Pfade beginnen mit `worlds/lego_city_undercover/...`.
3. Bei Bedarf die native DLL gemäß bisheriger Projektanleitung bauen:

   ```powershell
   .venv\Scripts\python.exe worlds\lego_city_undercover\tools\build_item_bridge.py
   ```

   Dies benötigt `ziglang` in der Python-Umgebung. Existiert bereits eine kompatible DLL mit `build/lego_city_undercover/native_items_build.json`, kann sie weiter genutzt werden.
4. `worlds\lego_city_undercover\tools\StartLCUNativeClient.cmd` doppelklicken. Das Konsolenfenster bleibt sichtbar, damit Startfehler nicht verschwinden. Alternativ von der Repository-Wurzel:

   ```powershell
   .venv\Scripts\python.exe worlds\lego_city_undercover\tools\native_client_gui.py
   ```
5. Server, Port, exakten AP-Slotnamen und optionales Serverpasswort eingeben. Anschließend **Verbinden**. Der Native-Modus benötigt Windows x64, die passende DX11-EXE und die gebaute native DLL. Für eine read-only AP-Verbindung kann „Native Items“ deaktiviert werden.
6. Die Save-Datei wird automatisch über den **geladenen** Charakterbestand ermittelt, sofern genau ein passender Steam-Slot existiert. Andernfalls per **Durchsuchen** die geladene `gameN.legocityundercoversavegamedata` auswählen. Bei Save-Konflikten stoppt die native Lieferung und das Log nennt den Grund.

## GUI-Funktionen

- **Verbindungsanzeige:** AP-Verbindung, geladenes Spiel/Outfit, native Save-Datei, bereits bestätigte Checks und empfangene AP-Items.
- **Live-Log:** Fehlermeldungen, erkannte Checks, native Vergaben, Save-Bestätigungen, Warnungen. Kopieren und Leeren.
- **Lokale Item-Tests:** Items suchen, auswählen, **Geben** oder **Nehmen**. Nur für bereits implementierte native Effekte, bei bestehender AP-Verbindung, geladenem Spieler im normalen Spielzustand und gebundener Save-Datei. Vor der ersten Teständerung erscheint eine Sicherheitsbestätigung.
- **Testfreigaben zurücksetzen:** Entfernt lokale Testregeln und übergibt die Kontrolle wieder an die echten AP-Receipts. **Nicht** als allgemeine Spielstand-Zurücksetzung gedacht: Währungsänderungen werden nicht automatisch rückgängig gemacht.
- **Einstellungen:** Server/Port/Slot, zuletzt ausgewählter Save-Pfad und die zwei Optionen werden lokal in `build/lego_city_undercover/native_client_ui.json` gespeichert. **Das Passwort wird nicht gespeichert.**
- **Trennen:** Stoppt die asynchrone Verbindung und wartet auf das Ende des Client-Workers, bevor das Fenster geschlossen wird.

## Wichtig / aktuelle technische Grenzen

- Die native Spieleintegration bleibt **experimentell**. Sie unterstützt ausschließlich die im Repository angegebene Version von `LEGOLCUR_DX11.exe` (SHA-256 `624fed07274bbd105d1d571ecb97a290df6f6f0aff76898c516890da6d136f76`).
- Die GUI allein löst **keine** fehlenden Story-/Area-Zugangssperren, nicht verifizierte Item-Bindings oder unvollständige Generierungslogik.
- Die Native-Tests verändern wirklich das Spiel. Die Auto-Save-Logik kann Änderungen persistieren. Zur Sicherheit **separaten Test-Spielstand** verwenden.
- Kein eigenständiger `.exe`-Client wird mitgeliefert; die GUI verwendet die vorhandene Python-Umgebung und den eingebauten Netzwerkclient.
- Native Hooks und Windows-DLL-Aufrufe konnten ohne laufendes Spiel/Windows nicht live geprüft werden. Diese Änderung verbessert die GUI und Ereignisverdrahtung, **nicht** die bestehende native C++-Implementierung.

## Tests

```powershell
.venv\Scripts\python.exe -m unittest worlds.lego_city_undercover.tests.test_native_client_gui -v
```

Für Headless-Linux lokal mit einer virtuellen X-Anzeige:

```bash
xvfb-run -a python -m unittest discover -v -s worlds/lego_city_undercover/tests -p test_native_client_gui.py
```

Die GUI-Tests prüfen reine UI-/Validierungslogik. Sie starten oder verändern kein laufendes LEGO-Spiel.
