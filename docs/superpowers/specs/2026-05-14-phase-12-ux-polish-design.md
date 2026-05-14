# Phase 12 — UX Polish (Design Spec)

**Status:** Approved, ready for plan
**Datum:** 2026-05-14
**Vorgänger-Phase:** 11 (Responsive UI)
**Nachfolger-Kandidaten:** Spaced Repetition, Foto-OCR, Karteikarten

## 1. Zweck & Motivation

Nach manuellem Walk-Through der App nach Phase 11 hat Matthias vier konkrete UX-Pain-Points entdeckt:

1. **Navigation aus Test heraus ist unklar**: der "Pausieren"-Button im Runner und das Fehlen eines Menü-Buttons auf der Review-Seite verwirren.
2. **Profile-Bearbeiten öffnet ein separates OS-Fenster** (QDialog-Verhalten) — bricht die "Ein-Fenster"-Metapher der App.
3. **Avatar-Emoji-Auswahl** ist überflüssig — User will nur Foto-Upload, sonst generisches Placeholder-Icon.
4. **Profile-Picker zeigt alle Karten in einer Zeile** bei breitem Fenster — Verteilung wirkt unausgewogen.

Phase 12 fixt diese vier Punkte als fokussierte Polish-Phase. **Keine Datenmodell-Änderungen**, keine neuen Domain-Module — primär UI-Refactoring + ein neues Page-Widget.

**Bewusst nicht in Phase 12** *(future work)*:
- Migration der `users.avatar` (TEXT-Emoji) Spalte — Spalte bleibt nullable im Schema, wird nur in UI ignoriert
- Re-Design des Profile-Picker-Layouts darüber hinaus (z.B. List-View)
- Avatar-Cropping / Bild-Bearbeitung beim Upload
- Spaced Repetition (eigene Phase)

## 2. Datenmodell — keine Änderungen

Phase 12 ist **reine UI-Refactoring-Phase**:
- Keine neue Migration
- Keine neuen Repos
- Keine Domain-Module
- `users.avatar` TEXT-Spalte bleibt im Schema, wird aber von der neuen Edit-Page nicht mehr gesetzt und von Display-Widgets ignoriert

## 3. Komponenten

### 3.1 Navigation-Fixes

**`pages/runner.py`**:
- Existierender `abort_btn` mit Label "Pausieren" wird umbenannt zu "Zurück zum Menü"
- Tooltip hinzufügen: `setToolTip("Fortschritt wird gespeichert — du kannst später weitermachen")`
- Verhalten unverändert: zeigt Bestätigungs-Dialog, ruft `window.show_menu()` + speichert attempt als incomplete

**`pages/review.py`**:
- Neuer Button "← Zurück zum Menü" neben dem bestehenden "Weiter üben"
- Click: `self.window.show_menu()`
- Object-name: `text` (Sekundär-Style, da "Weiter üben" die Primary-Action bleibt)

**Results-Page** unverändert — `return_from_results()` funktioniert korrekt.

### 3.2 ProfileEditPage als Inline-Page

**Neue Datei** `src/school_test_engine/ui/pages/profile_edit.py`:

```python
class ProfileEditPage(QWidget):
    def __init__(self, window, conn: sqlite3.Connection):
        ...
    
    def show_for(self, user_id: int | None = None, return_to: str = "picker") -> None:
        """Configure the page for create (user_id=None) or edit (user_id given)."""
        self._user_id = user_id
        self._return_to = return_to
        self._load_initial_values()
```

**Layout**:
- Header: `← Zurück`-Button (links) + Eyebrow "PROFIL" + Title ("Neues Profil" oder "Profil bearbeiten") + (rechts) "Speichern"-Button
- Form-Bereich (Scrollbar via QScrollArea):
  - Name (QLineEdit)
  - Foto-Upload-Block (Avatar-Vorschau + Button "Foto auswählen…")
  - Geburtsdatum (QDateEdit mit "Löschen"-Option)
  - KI-Stil-Hinweis (QPlainTextEdit, optional) — Phase 8
  - Schul-Kontext-Sektion — Phase 9 (Klassenstufe-Combo, Schultyp-Combo, Bundesland-Combo, Schul-Name, Schuljahr)
- Footer: "Speichern"-Button (primary) + "Abbrechen" + (nur Edit-Modus) "Löschen" (danger)

**Save-Flow**:
1. Validate (Name nicht leer)
2. Wenn `user_id is None`: `users_repo.create_user(...)` + alle anderen Felder via `update_user`
3. Sonst: `users_repo.update_user(user_id, ...)` mit allen Feldern
4. Navigate via `self.window` zurück:
   - `return_to == "picker"`: `self.window.show_profile_picker()`
   - `return_to == "manager"`: `self.window.show_profile_manager()`
   - `return_to == "menu"`: `self.window.show_menu()`

**Delete-Flow** (nur Edit-Modus):
- Bestätigungs-Dialog (`QMessageBox`)
- Wenn ja: `users_repo.delete_user(user_id)`
- Wenn aktiver User gelöscht wurde: zurück zum Profile-Picker (force user-selection)
- Sonst: zurück zum `return_to`

**Cancel-Flow**: einfach navigate zurück, keine Änderungen speichern.

### 3.3 MainWindow Integration

Neue Methode:
```python
def show_profile_edit(self, user_id: int | None = None, return_to: str = "picker") -> None:
    self.profile_edit_page.show_for(user_id, return_to)
    self.stack.setCurrentWidget(self.profile_edit_page)
```

Page-Registrierung in `__init__`:
```python
self.profile_edit_page = ProfileEditPage(self, conn)
...
self.stack.addWidget(self.profile_edit_page)
```

### 3.4 ProfileManagerPage Refactoring

In `pages/profile_manager.py`:
- `_ProfileEditDialog`-Klasse wird **komplett entfernt**
- `ProfileManagerPage._create()`: ruft `self.window.show_profile_edit(user_id=None, return_to="manager")` statt `dlg.exec()`
- `ProfileManagerPage._edit(user_id)`: ruft `self.window.show_profile_edit(user_id=user_id, return_to="manager")`
- `ProfilePickerPage` analog: "Neues Profil"-Tile ruft `show_profile_edit(None, return_to="picker")`, Edit-Aktion (falls vorhanden) ruft mit user_id

### 3.5 Avatar: Generic Placeholder Strategy

**Entfernt** aus Edit-Page (vorher in `_ProfileEditDialog`):
- `COMMON_AVATARS = ["👤", "🧒", ...]`-Konstante
- `AvatarTile`-Grid (12 Emoji-Tiles)

**Behält** in Edit-Page:
- Avatar-Vorschau (zeigt entweder Foto oder Placeholder)
- "Foto auswählen…"-Button
- "Foto entfernen"-Button (falls Foto da ist)

**Display-Logik in `widgets/avatar_badge.py` und `widgets/profile_card.py`**:
```python
# Pseudo:
if image_bytes:
    render_photo(image_bytes, diameter)
else:
    render_generic_placeholder(diameter)
```

**Generic Placeholder Design**:
- Paper-50-getönter Kreis (`#f4efe6`) als Background
- Subtle person-silhouette (z.B. Unicode `👤` in `#b3a98e`-grau, oder ein einfacher SVG-Path) zentriert
- Diameter parametrisierbar (gleicher Parameter wie photo-rendering)

**Implementierung**: Erweitere `avatar_badge.py` und `profile_card.py` mit einer `_render_placeholder(painter, rect)`-Methode. Die existierende `image_bytes`-First-Logik bleibt — nur der Fallback ändert sich (kein Emoji-Text mehr, sondern grafischer Placeholder).

**Wichtig**: bestehende User mit Emoji-Avatar (`users.avatar = "🧒"` z.B.) sehen NACH Phase 12 den Placeholder statt des Emojis. Die `users.avatar`-Spalte in der DB bleibt unverändert (nullable TEXT) — keine Migration.

### 3.6 Profile-Picker Layout-Constraint

In `pages/profile_picker.py`, am `grid_container` (oder dem äquivalenten Container, der die FlowLayout-Karten umschließt):
```python
grid_container.setMaximumWidth(880)  # 3 Karten × 280px (max card width) + 2 × 20 (h_spacing)
```

Effekt: FlowLayout in einem 880px-breiten Container wraps automatisch alle 3 Karten in die nächste Zeile. Bei 5 Profilen → 3 + 2 Karten in 2 Zeilen. Bei 7+ → 3 Zeilen.

Container bleibt mittig zentriert (existierender `addStretch(1)`-Wrapper).

## 4. Tests

**Unit-Tests** (Profile-Edit-Page macht es testbar):
- `test_profile_edit_page.py`:
  - Create-Modus: leere Felder beim Start
  - Edit-Modus: lädt User-Daten aus DB
  - Save in Create-Modus erstellt User + setzt Felder
  - Save in Edit-Modus aktualisiert User
  - Cancel speichert nichts
  - Delete entfernt User + Cascade
  - return_to="picker"/"manager"/"menu" routes korrekt

**Smoke-Tests**:
- Runner-Page hat Button "Zurück zum Menü" (statt "Pausieren")
- Review-Page hat zweiten Button "Zurück zum Menü"
- AvatarBadge ohne image_bytes rendert keinen Emoji-Text mehr
- ProfileCard ohne image_bytes rendert keinen Emoji
- Profile-Picker-Container hat maximumWidth = 880

## 5. Akzeptanzkriterien

1. Runner-Page Button-Label = "Zurück zum Menü" mit Tooltip
2. Review-Page hat zusätzlichen "Zurück zum Menü"-Button
3. `ProfileEditPage` existiert im MainWindow-Stack
4. Profile-Manager `_create` und `_edit` routen via `show_profile_edit`, nicht via `dlg.exec()`
5. Profile-Picker "Neues Profil"-Tile routet via `show_profile_edit(None, "picker")`
6. `_ProfileEditDialog`-Klasse ist entfernt
7. ProfileEditPage hat KEINE Emoji-Tile-Auswahl, nur Foto-Upload
8. `AvatarBadge` + `ProfileCard` zeigen generischen Placeholder bei NULL `avatar_image`
9. Profile-Picker-Container `setMaximumWidth(880)`
10. Alle 234 bestehenden Tests grün, neue Unit-Tests grün

## 6. Edge Cases

| Fall | Verhalten |
|------|-----------|
| Bestehender User mit Emoji-Avatar (z.B. Clemens 🧒) | Nach Phase 12: Placeholder wird angezeigt. `users.avatar`-Wert bleibt in DB unverändert (zukünftig könnten wir es ganz löschen via Migration) |
| Create-Modus, User klickt "Speichern" mit leerem Namen | QMessageBox.warning "Bitte Namen vergeben", bleibt auf Page |
| Edit-Modus, User löscht aktiv-User | Force Profile-Picker (kein aktiver User mehr → Picker-Pflicht) |
| Cancel im Create-Modus | Routes zurück zu return_to, kein User angelegt |
| Page-Wechsel ohne Save (z.B. via Hamburger-Menu) | Unsaved changes gehen verloren — kein Confirm-Dialog (akzeptiert, simple UX) |
| Foto-Upload mit ungültiger Datei | QFileDialog filtert auf Bild-Typen, plus try/except mit Error-Message |
| Save im Edit-Modus aktualisiert nur diff'd Felder | Sentinel-Pattern in `update_user` greift schon |

## 7. Risiken

- **AvatarBadge wird an mindestens 3 Stellen genutzt**: ProfileCard (Profile-Picker + Profile-Manager-Liste), Profile-Chip im Hauptmenü-Top-Bar, AvatarTile im Avatar-Picker (wird in Phase 12 entfernt). Alle müssen konsistent Placeholder anzeigen. Mitigation: zentrale Logik in `avatar_badge.py`.
- **ProfileEditPage muss alle Felder von `_ProfileEditDialog` haben**: Phase 8 (ai_style_briefing), Phase 9 (5 school-context fields), Phase 6C (birthday). Risk: Field vergessen beim Extract. Mitigation: Side-by-side-Vergleich mit altem Dialog beim Implementieren.
- **Bestehende Tests die `_ProfileEditDialog` direkt benutzen** (falls vorhanden) brechen. Mitigation: Check `grep _ProfileEditDialog tests/` vor dem Refactoring.
- **Profile-Picker 880px max-width auf sehr breitem Display**: Container ist zentriert, Whitespace links/rechts. Akzeptiert — fokussierter Look statt Strecken.
