# Native Anzeigen für AP-Items

Stand: 2026-11-14. Statische Untersuchung von 745 extrahierten SF-Skripten
und der gepinnten Windows-EXE. Keine Popup-Funktion im laufenden Spiel aufgerufen.
Das ist kein Nachweis, dass sämtliche intern kompilierten Anzeigen erfasst sind.

## Geeignete Kanäle

| System | Skriptstellen | Bewertung |
| --- | ---: | --- |
| UnlockSequence | 9 | Bester Kandidat für zentrale Progression-Anzeige, ohne die zusätzliche Animationsvariante |
| UnlockSequenceAndAnim | 20 | Originale Freischaltungsanzeige; mögliche zusätzliche Animation/Spielerbeeinflussung vermeiden |
| UI_SetMissionHelpText | 184 | Kandidat für kleine HUD-Anzeige; Position und Nichtblockieren noch live bestätigen |
| UI_SetMissionMessage | 69 | Zweiter zeitgesteuerter HUD-Kandidat; tatsächliche Bildschirmposition live vergleichen |
| UI_ShowObjectiveScreen | 124 | Missionsanzeige; Konflikte mit laufender Story |
| UI_ShowMissionPrompt | 15 | Aktivitätsdialog mit Bestätigung; ungeeignet für gewöhnliche Item-Eingänge |
| UI_ShowSummaryScreen / UI_ShowLevelSummaryScreen | 5 / 3 | Abschlussanzeige; ungeeignet während des Spiels |
| SetHint / CancelHint | 599 / 425 | Bestehender Hinweis-Kanal; Story und Tutorials dürfen nicht verdrängt werden |
| SetHintIconDRC | 62 | Begleitende Hinweis-Symbole; kein nachgewiesener allgemeiner Item-Toast |
| PrintToScreen | 229 | Debug-Ausgabe; keine geeignete fertige Produktionsanzeige nachgewiesen |
| UI_ShowMapUnlock | 0 | Native Registrierung vorhanden; keine Skriptbeispiele im extrahierten Bestand |

AwardCharacter und CommitCollectables sind ebenfalls inventarisiert, aber keine
reinen Anzeige-APIs. Keine künstliche Vergabe verwenden, um ein Popup auszulösen.

## Nachgewiesener nativer Pfad

UnlockSequence (RVA 0x905f0) und UnlockSequenceAndAnim (0x906d0) lesen zwei
Skriptargumente aus und senden einen gleich aufgebauten Datenblock an 0x1d8800.
Die Variante unterscheidet sich im hier untersuchten Wrapper durch ein Bool-Feld
am Stackoffset 0x59 (false/true). Beide Wrapper schreiben selbst keine
Item-Besitzflags. Der aufgerufene Empfänger und seine Folgewirkungen sind damit
noch nicht vollständig untersucht.

Beispiele: `UnlockSequence("MechIcon_Camera", "GENERIC_UNLOCK_CAMERA")` und
`UnlockSequenceAndAnim("MechIcon_DetectiveMode", "ABILITY_DETECTIVE_MODE")`.
Die Argumente sind Symbolname und Textschlüssel. Beliebiger deutscher Text ist
dadurch noch nicht nachgewiesen: Lokalisierungsauflösung und Lebensdauer eigener
Strings müssen vor einer Bridge-Implementierung geklärt werden.

UI_SetMissionHelpText (0x10cf40) und UI_SetMissionMessage (0x10d0b0) führen in
den gemeinsamen HUD-Pfad 0x20e360, mit verschiedenen Kanalwerten 2 beziehungsweise 3.
Die Wrapper unterstützen einen numerischen Zeitparameter; Skripte verwenden
beispielsweise 4. Die Anzeige wird separat über UI_RemoveMissionHelpText
(0x10c650) und UI_RemoveMissionMessage (0x10c700) entfernt.
Kanalnummern belegen keine konkrete Bildschirmposition.

Diese RVAs sind Skript-Handler mit VM-Kontext, keine Funktionen, denen die Bridge
einfach einen C-String übergeben darf. Eine solche Verwechslung wäre absturzgefährlich.

`AwaitUnlockSequenceFinished` ist in goto_farm.sf ein selbst definierter
Skriptzustand, keine native Popup-Funktion. Dort wartet das Skript auf das Ende
des Spieler-Kontexts UnlockDisguise; dies betrifft die Verkleidungssequenz und
belegt keine generelle Modalität von UnlockSequence.

## Vorgesehene Verwendung

* Progression: zentrale UnlockSequence mit konkretem aufgelöstem Effekt,
  z.B. „Wurfhakenkanone erhalten“, auch bei einem Progressive-Police-Item.
* Useful/Filler: kürzere HUD-Meldung; den unteren, nicht blockierenden Kanal
  erst nach visuellem Vergleich der beiden HUD-Kandidaten festlegen.
* Eine lokale FIFO-Warteschlange verhindert überlagerte AP-Anzeigen.
  Währungsserien können zusammengefasst werden.
* Während Ladebildschirmen, Cutscenes, Menüs und nativen Freischaltungsanzeigen
  warten; belegte Story-Hinweiskanäle nicht überschreiben oder entfernen.
* Anzeige vom Grant-/Speicherergebnis trennen: ein Popup bestätigt keinen Save.
* Der Client zeigt Eingänge weiterhin an, falls die native Anzeige nicht verfügbar ist.

## Reproduzierbare Recherche

`tools/research_popup_systems.py` erstellt `notes/analysis/popup_systems/calls.csv`
und `catalogue.json`, einschließlich EXE-SHA256 und Handler-Kandidaten.
Handler-Adressen stammen aus Name-Getter-/Tabellenreferenzen; die oben erläuterten
vier Anzeige-Wrapper wurden zusätzlich disassembliert.

## Implementierte erste Version (historisch; Korrektur unten)

Client und native Bridge besitzen jetzt eine echte HUD-Anbindung (Opcode 19).
Sie nutzt den Literaltext-Einstieg 0x205b20 statt des Lokalisierungs-Einstiegs
0x20e360. Dessen Textsetter 0x1e9580 kopiert den Text in eine Spiele-Allokation;
die Bridge liest den kopierten Text vor der Bestätigung zurück. Es bleiben keine
Zeiger auf die temporäre DLL oder die Shared-Memory-Nachricht zurück.

Progression verwendet Kanal 3 für sechs Sekunden, Useful/Filler Kanal 2 für drei
Sekunden. Das ist bewusst noch **nicht** die zentrale UnlockSequence mit Symbol:
deren sichere dynamische Textübergabe bleibt offen. Die tatsächliche Position und
Größe der beiden HUD-Kanäle ist ebenfalls noch nicht visuell bestätigt. Diese
erste Implementierung macht daher keine Zusage einer exakt mittigen/unteren Position.

Die Bridge fordert normalen Spieler-Kontext, lebenden Actor, Spiel im Vordergrund,
vorhandene HUD-Objekte und beide Nachrichtenkanäle im beobachteten Ruhezustand 7.
Sie wartet bei ausstehenden nativen Unlock-Events. Die Belegungsprüfung erfolgt
auf dem Spielthread direkt vor dem Aufruf. Sie entfernt keine Story-Meldungen;
eine später eintreffende Story-Meldung kann hingegen den AP-Text unterbrechen.
Der Kontext allein ist kein vollständiger Nachweis sämtlicher Pause-/Menüzustände.

`item_popups.py` und die Journal-Tabelle `item_popups` verwalten die FIFO-Eingänge
pro Seed/Slot. Anzeigen warten auf die RAM-Vergabe, sind aber unabhängig von der
Save-Bestätigung. Bereits vor dem Upgrade gespeicherte Items werden nicht erneut
angezeigt. Reconnects erhalten wartende Meldungen. Bei ungewissem RPC-Ergebnis oder
Abbruch während der Übergabe wird eine Anzeige nicht automatisch wiederholt;
dies verhindert Doppelanzeigen, kann aber eine rein kosmetische Meldung verlieren.
Die Item-Zustellung bleibt davon unabhängig.

Die Oberfläche hat „Item-Popups im Spiel“ sowie „Progression testen“ und
„Useful / Filler testen“. Der Schalter gilt auch während einer Verbindung.
Beide Vorschauen ändern keine Items, Entitlements, Empfangsmarker oder Save-Flags.
Der Konsolenclient unterstützt `--disable-item-popups`.

Nach dem Neubau nur den Client neu starten; anschließend Vorschau anklicken und
ins Spiel zurückwechseln. Der native Aufruf wartet bei belegten HUD-Kanälen.
Neuer Seed, neue YAML und neuer Spielstand sind dafür nicht notwendig.

Validierung: 245 Regressionstests, 244 bestanden, einer übersprungen, einschließlich
echter Tk-Tests. Neue Tests decken UTF-8-Limits, Text-Tag-Entfernung, Kontext-/Off-Schalter,
belegte Kanäle, Reconnects, ungewisse Timeouts und vergabefreie Vorschauen ab.
Die versionierte DLL wurde erfolgreich gebaut und per Quellen-/Binärhash geprüft.
Es wurde bisher keine Vorschau im laufenden Spiel ausgelöst.

## Korrektur nach Spieltest des Nutzers

Der Nutzer bestätigt den frei stehenden Text von Kanal 3 mit der
Wurfhakenkanonen-Vorschau. Kanal 2 zeigt dagegen Kriminellenscan-Hinweistext und
wird für AP-Meldungen nicht mehr benutzt. Alle Klassen verwenden nun Kanal 3;
Progression bleibt sechs Sekunden sichtbar, alle anderen Klassen drei Sekunden.
Die Oberfläche bietet getrennte Vorschauen für Progression, Useful und Filler.

Popup-Paketversion 2 übergibt die tatsächliche Klassifizierung, nicht nur ein
Progression-Bool. Bestehende Journal-Datenbanken werden migriert; wartende
Useful-Meldungen bekommen beim erneuten Abgleich ihre richtige Klasse, ohne
bereits abgespielte Anzeigen zu wiederholen.

Textfarbe: Progression #af99ef, Useful #6d8be8, Filler #00eeee, Trap #fa8072.
Die RGB-Bytes am Textobjekt +0xc8..0xca sind über Konstruktor 0x1e6b30,
Farbsetter 0x1e93d0 und Renderer 0x1e83b0 nachvollzogen. Ein lesender Live-Abgleich
ergab die ursprüngliche blaue Farbe #4aadff passend zur Nutzeraufnahme.
Der native Setter bekommt nur dieses Textobjekt, ohne rekursive Kindänderungen.

Ein Timer auf dem Spielthread stellt die ursprünglichen RGB-Werte bei Ablauf,
Textwechsel oder inaktivem Kanal wieder her. Alpha bleibt unter Kontrolle der
nativen Einblendanimation. Ein ersetztes HUD/Textobjekt und eine zwischenzeitlich
geänderte native Farbe werden nicht überschrieben. Die versionierte Bridge-DLL
wird für die Callback-Lebensdauer im Spielprozess festgehalten. Es werden keine
Spiel-Dateien, Item-Besitzflags oder Saves für diese Farbe verändert.

Die neuen Farben sind noch nicht visuell vom Nutzer bestätigt. Validierung:
251 Tests, 250 bestanden, einer übersprungen. Dazu gehören zwei native Tests der
echten Farbrücksetzung auf künstlichem Speicher (Alpha erhalten, neuere Farbe
erhalten, Objektwechsel, Timerablauf) und elf Popup-Queue-/Migrationstests.

## Empfang, eigene Funde, Versand und tiefere Position

Der Nutzer hat die Klassenfarben im Spiel bestätigt. Die Texte lauten jetzt:

* `You received [itemname] from [playername]!`
* `You found your own [itemname]!`
* `You sent [itemname] to [playername]!`

Empfang verwendet den Sender aus dem indizierten NetworkItem. Eigene Funde werden
nur dort angezeigt, nicht zusätzlich als Sendemeldung. Versand verwendet ausschließlich
die strukturierte Serverbestätigung `PrintJSON`/`ItemSend`, nicht einen geratenen
Location-Inhalt. Der Itemname wird im Spiel-Datenpaket des Empfängers aufgelöst;
die Farben stammen aus den Item-Flags der Servermeldung.

Bestätigte Sendungen haben eine eigene dauerhafte Journal-Warteschlange mit
Schlüssel aus Fundslot, Location, Empfänger und Item. Wiederholte Servermeldungen
und Reconnects erzeugen keine doppelten Versandanzeigen. Ereignisse vor
Journalinitialisierung werden samt Seed/Team/Slot vorgehalten und erst dem passenden
Journal übergeben. Sendungen lösen keine lokale Item-Vergabe aus.

Das native Textobjekt besitzt aktuelle lokale Y-Position bei +0x74 und deren
Layout-Vorgabe bei +0xb4 (nachvollzogen über 0x1e67d0 und 0x1e90f0). Beide werden
während der AP-Meldung um 240 logische Einheiten nach unten verschoben, mit dem
nativen Layout-Dirty-Bit (+9, Bit 1). Nach der Meldung stellt die vorhandene
Style-Lease beide Werte wieder her, sofern sie weiterhin unseren Werten entsprechen.
Eine inzwischen vom Spiel gesetzte andere Position wird beibehalten. Die neue
Bildschirmposition ist implementiert, aber noch nicht visuell bestätigt.

Die drei Vorschauknöpfe demonstrieren jetzt Empfang, Versand und eigenen Fund.
257 Tests: 256 bestanden, einer übersprungen. Neue Tests umfassen exakte Texte,
Empfänger-Spielauflösung, eigene Funde ohne Versand-Duplikat, persistente Sendungen,
Klassenflags und die native Rücksetzung der Y-Position auf künstlichem Speicher.

Nach weiterem Nutzerfeedback beträgt der Y-Versatz jetzt 280 statt 240 logische
Einheiten. Das sind weitere 40 Einheiten nach unten; der Rücksetzmechanismus bleibt gleich.

## Fahrzeug-, Speicher- und Modal-Anzeigen

Nach Nutzerfeedback wurde die kosmetische Anzeige von der nativen Item-Vergabe
entkoppelt: Eine AP-Empfangsmeldung bestätigt den Serverempfang und wartet nicht mehr
auf sichere RAM-Vergabe oder Save-Verifikation. Die Start-Historie bereits gespeicherter
Items wird weiterhin nicht neu eingereiht. Eigentliche Grants behalten alle bisherigen
Kontext- und Save-Sperren.

Nur Popup-Opcode 19 darf zusätzlich in RideAlong (11), DropPoint (27) und RideObject
(157) laufen. Kampf, Tod, Laden und andere ungeprüfte Kontexte bleiben ausgenommen.
Vorschauknöpfe benötigen jetzt ein verbundenes, geladenes Spiel, aber weder einen
zu Fuß stehenden Spieler noch eine abgeschlossene Save-Bindung.

Die Bridge prüft vor dem Textsetter zusätzlich dessen originale Screen-Ownership-
Bedingungen (0x204170, Manager-Pointer RVAs 0x1803d98 und 0x1803da0). Bei einem
modal belegten Bildschirm wird nicht angezeigt und die Nachricht bleibt queued.
Nach dem Setter bedeutet ein unverändert ruhender Kanalzustand 7 ebenfalls
„nicht angezeigt“; ein kopierter Text allein bestätigt keine Übergabe mehr.
Zeitweilig fehlende HUD-Manager sind ein sicherer Wiederholungsfall, kein ungewisser
RPC-Timeout. Echte ungewisse Timeouts werden weiterhin nicht blind wiederholt.

Andere native Popups werden nicht überschrieben. Nach deren Ende wird der nächste
Warteschlangeneintrag versucht; ein blockierter HUD-Kanal wird einmalig geloggt.
273 Tests liefen, 272 bestanden und einer wurde übersprungen. Dazu gehören
Fahrzeug-Kontexte ohne erweiterte Grant-/Lock-Rechte, Anzeigen vor Native-Grants und
native Screen-Ownership-Fälle auf künstlichem Speicher. Die visuelle Bestätigung
im fahrenden Spiel und während eines Autosaves steht noch aus.
