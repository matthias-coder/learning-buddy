# Bugreport – Learning Buddy 1.0.1

Findings from the first functional test of 1.0.1: manual test by Matthias (#1–#2) plus an automated
exploratory test (headless, temporary database, no code changes) on 2026-10-04.
Status: `offen` · `behoben (Version)` — #1–#6 and #9 fixed on branch `fix/1.0.2` (not released yet).

## Übersicht

| #  | Bereich           | Kurzbeschreibung                                                                 | Schwere | Status          |
|----|-------------------|----------------------------------------------------------------------------------|---------|-----------------|
| 1  | Profile verwalten | Kein Zurück-Knopf, Esc wirkungslos – Seite lässt sich nicht verlassen             | hoch    | behoben (1.0.2) |
| 2  | Profil anlegen    | Speichern/Abbrechen ohne Wirkung, Mehrfachklick legt Duplikate an                | hoch    | behoben (1.0.2)           |
| 3  | Ergebnis-Seite    | Zurück/Esc führt in den alten Test und legt einen neuen leeren Versuch an        | hoch    | behoben (1.0.2)           |
| 4  | Import            | KI-Antwort mit ```json-Block oder Begleittext scheitert; Fehler englisch/kryptisch | mittel  | behoben (1.0.2)           |
| 5  | Termine           | „Synchronisieren“-Knopf bleibt nach Sync grau                                    | mittel  | behoben (1.0.2)           |
| 6  | Noten             | Note 6,5 lässt sich speichern                                                    | mittel  | behoben (1.0.2)           |
| 7  | Profil bearbeiten | Kopfleiste zeigt nach Umbenennen/Fotowechsel des aktiven Profils alte Daten       | mittel  | offen           |
| 8  | iCal-Sync         | Fehlgeschlagener Hintergrund-Sync blockiert neuen Versuch für 24 h               | niedrig | offen           |
| 9  | Import            | Datei mit falscher Kodierung (nicht UTF-8) → unbehandelter Fehler, keine Meldung | niedrig | behoben (1.0.2)           |
| 10 | Bibliothek        | Mehrere pausierte Tests: Banner zeigt nur den neuesten                           | niedrig | offen           |
| 11 | Prompt-Builder    | Platzhalter `<Klasse>`/`<Schultyp>` bleiben im Prompt, wenn Profil sie nicht hat | niedrig | offen           |
| 12 | Kleinkram         | Diverse UI-/Validierungsdetails, siehe unten                                     | niedrig | offen           |

---

## #1 – „Profile verwalten“: Zurück-Knopf fehlt

- **Gemeldet:** 2026-10-04 (manuell)
- **Schritte:** App starten → Profilauswahl → „Profile verwalten →“
- **Ist:** Es gibt keinen Zurück-Knopf und keine Kopfleiste, Esc wirkt nicht. Man muss die App neu starten.
- **Soll:** Ein „← Zurück“-Knopf führt zur Profilauswahl bzw. ins Hauptmenü.
- **Ursache:** Im Picker-Modus ist die globale Kopfleiste ausgeblendet. Die Seite hat keinen eigenen Zurück-Knopf (`_back()` ist an nichts angeschlossen). `_on_esc_pressed` (`main_window.py`) reagiert nur, wenn der Zurück-Knopf der Kopfleiste sichtbar ist. Dadurch wirkt Esc auch auf der Bearbeiten-Seite nicht, solange man aus der Profilauswahl kommt.
- **Fix (vorbereitet, nicht committet):** „← Zurück“-Knopf in `ui/pages/profile_manager.py`, Test `tests/test_profile_manager_page.py`. Esc ist damit noch nicht gelöst.

## #2 – Profil anlegen: kein Feedback, Seite bleibt offen, Duplikate

- **Gemeldet:** 2026-10-04 (manuell, automatisiert bestätigt)
- **Schritte:** Profilauswahl → Kachel „Neues Profil“ → ausfüllen → „Speichern“ (mehrfach) oder „Abbrechen“
- **Ist:** Das Profil wird gespeichert, aber die Seite bleibt stehen, und es kommt keine Meldung. Jeder weitere Klick legt ein weiteres Profil an (im Test 3× „Dora“). „Abbrechen“ und Esc tun nichts, es gibt keinen Ausweg.
- **Soll:** Nach dem Speichern erscheint eine kurze Bestätigung, dann geht es zurück zur Profilauswahl. „Abbrechen“ führt ebenfalls zurück.
- **Ursache:** `ProfileEditPage` ruft `window._navigate_back()` auf. In der Historie liegt `profile_picker`, das kein Ziel in `_dispatch` ist, deshalb kehrt die Methode stillschweigend zurück. `_user_id` bleibt `None` → bei jedem Klick läuft `create_user` erneut.
- **Fix-Idee:** `profile_picker` als Navigationsziel aufnehmen; das löst #1 und #2 an der Wurzel und macht Esc im Picker-Modus nutzbar. Dazu eine Speicher-Bestätigung und einen Schutz gegen Mehrfachklick.
- **Hinweis:** Die Testprofile „efwf“ liegen mehrfach in der echten Datenbank und lassen sich über „Profile verwalten“ löschen.
- Nicht als Bug gewertet: Der Geburtstag 1.1.1900 ist nur ein interner Platzhalter und wird als „leer“ gespeichert. Der „Löschen“-Link neben dem Geburtstag leert nur das Datum. Er ist aber leicht mit „Profil löschen“ zu verwechseln, siehe #12.

## #3 – Ergebnis-Seite: Zurück führt in den alten Test

- **Schritte:** Bibliothek → Test starten → durchklicken → „Abgeben“ → auf der Ergebnis-Seite Esc oder Zurück drücken, dann noch einmal Esc.
- **Ist:** Zuerst erscheint die Übersicht des schon abgegebenen Tests, danach startet der Test neu. Dabei wird ein neuer, leerer Versuch angelegt. Der taucht anschließend als „Pausiert“-Banner in der Bibliothek auf.
- **Soll:** Von der Ergebnis-Seite führt Zurück ins Menü bzw. in den Verlauf, nie zurück in den Test.
- **Ursache:** `_navigate` in `main_window.py` legt den Runner zwar nicht selbst auf den Stapel, setzt ihn aber als `_current`. Beim Wechsel zur Übersicht wandert er doch auf den Stapel, mit `action='start'`. Beim Zurückgehen startet `_render_runner` ihn dann neu.

## #4 – Import: KI-Antwort mit Codeblock/Begleittext scheitert

- **Ist:** Wird eine KI-Antwort mit ` ```json … ``` ` oder einem Satz wie „Hier ist dein Test:“ eingefügt, erscheint „Ungültiges JSON: Expecting value (Zeile 1, Spalte 1)“. Validierungsfehler kommen als englische Pydantic-Texte („Field required“, „Input should be …“).
- **Soll:** Codeblock-Markierungen und Begleittext werden automatisch entfernt. Fehler erscheinen auf Deutsch und kindgerecht („Bitte nur den Test-Teil kopieren“).
- **Ursache:** `importer/json_import.py` ruft `json.loads` ohne Bereinigung auf; `_format_validation_error` reicht die Pydantic-Texte durch.
- **Einschätzung:** Das ist der wahrscheinlichste Stolperstein im Alltag, weil KIs fast immer Codeblöcke liefern.

## #5 – „Synchronisieren“-Knopf bleibt grau

- **Schritte:** Profil mit Kalender-Link → Termine → „↻ Synchronisieren“ → warten → erneut klicken.
- **Ist:** Der Knopf bleibt deaktiviert, bis man die Seite wechselt.
- **Ursache:** `events.py` `_on_sync_done` aktiviert den Knopf und sendet dann `events_synced`. Darauf folgt `reload()` → `_update_sync_state()`. Weil der Sync-Thread zu diesem Zeitpunkt noch gesetzt ist, wird der Knopf dort wieder deaktiviert.

## #6 – Note 6,5 speicherbar

- **Schritte:** Note hinzufügen → „6“ → „,5“ → Speichern.
- **Ist:** 6,5 wird gespeichert und geht in den Schnitt ein.
- **Ursache:** `assessment_edit.py` `_toggle_half` prüft keine Obergrenze.

## #7 – Kopfleiste aktualisiert sich nicht nach Profiländerung

- **Ist:** Wird das aktive Profil umbenannt oder bekommt ein neues Foto, zeigt die Kopfleiste weiter den alten Stand.
- **Ursache:** `user_changed` ist nur mit dem Schulkalender verbunden; `header.set_user` wird nur bei `set_active_user` aufgerufen.
- **Hinweis:** Im eingeloggten Zustand gibt es aktuell gar keinen Weg zu „Profile verwalten“. Das Logo-Menü hat keinen Eintrag dafür, man muss über „Profil wechseln“ gehen.

## #8 – Fehlgeschlagener Hintergrund-Sync blockiert 24 h

- **Ist:** Schlägt der automatische Kalender-Sync beim Anmelden fehl (z. B. offline), gibt es 24 h lang keinen neuen Versuch.
- **Ursache:** `ical_sync/service.py` `_persist_error` setzt `ical_last_sync_at`. Die 24-h-Regel in `main_window.py` wertet das als erfolgreichen Sync.

## #9 – Import-Datei mit falscher Kodierung

- **Ist:** Eine nicht-UTF-8-Datei löst einen `UnicodeDecodeError` aus. Der Fehler wird nicht abgefangen, und der Nutzer sieht keine Meldung.
- **Ursache:** `importer/json_import.py` fängt nur `OSError`.

## #10 – Mehrere pausierte Tests

- **Ist:** Wer Test A pausiert und dann Test B pausiert, sieht im Bibliotheks-Banner nur B. A kommt erst wieder zum Vorschein, wenn man B verwirft.
- **Ursache:** `library.py` holt per `find_incomplete_attempt` nur einen Versuch.

## #11 – Prompt-Builder: Platzhalter bleiben stehen

- **Ist:** Ist im Profil keine Klasse und kein Schultyp gesetzt, stehen `<Klasse>`/`<Schultyp>` wörtlich im kopierten Prompt (vermutet).
- **Soll:** Sinnvolle Vorgaben verwenden oder darauf hinweisen, dass diese Angaben im Profil fehlen.

## #12 – Kleinkram

- Noten: Bestätigungsdialog „Note loeschen?“ / „endgueltig loeschen“ ohne Umlaute (`assessment_edit.py`).
- Noten: Punkte über dem Maximum (30 von 10) werden ohne Hinweis gespeichert. 0 Punkte gelten als „leer“.
- Termine: Ohne Kalender-Link steht nur „Schulkalender nicht verknüpft“ mit einem wirkungslosen Knopf, ohne Hinweis, wo man den Link einträgt.
- Termine: Wird ein Termin mit Note gelöscht, bleibt die Note ohne Warnung erhalten.
- Bibliothek: Dieselbe Datei lässt sich mehrfach importieren und erzeugt Duplikate.
- Profile: Sehr lange Namen schieben „Bearbeiten“/„Löschen“ aus dem Bild; es gibt keine Längenbegrenzung. Doppelte Profilnamen sind erlaubt.
- Profilformular: Der „Löschen“-Link am Geburtstag ist leicht mit „Profil löschen“ zu verwechseln. Besser „Zurücksetzen“.
- Speichern zeigt generell keine Bestätigung (Noten, Termine, Profile); die Seite springt nur zurück.

## Geprüft und in Ordnung

Login, Profilwechsel, alle Einträge im Logo-Menü inkl. Zurück/Esc. Test durchführen: Punkte und Noten stimmen, Pause/Fortsetzen, Rückfrage bei offenen Fragen, kein Duplikat bei doppeltem „Abgeben“. Verlauf, Lücken und Fehlerheft füllen sich; Üben aus Lücken/Fehlerheft. Drucken/PDF. Termine anlegen/bearbeiten/löschen inkl. Schaltjahr und Jahreswechsel. Notenschnitt. Kalender-Tabs und Ferien-Banner. iCal ohne Duplikate, verständliche Fehler bei kaputter URL/Antwort. Daten bleiben zwischen Profilen getrennt. Leere Zustände bei frischem Profil. Keine Abstürze außer #9.

Nicht geprüft: Daily-5/Cockpit. Die Optik ließ sich nicht prüfen, weil die Testumgebung keine Schriften rendert.
