# Phase 11 — Responsive UI (Design Spec)

**Status:** Draft, awaiting user approval
**Datum:** 2026-05-14
**Vorgänger-Phase:** 10 (Daily-5)
**Nachfolger-Kandidaten:** Phase 12 (Spaced Repetition), Foto-OCR, Direct AI-API-Calls, Karteikarten

## 1. Zweck & Motivation

Heute öffnet die App mit `window.resize(960, 720)` und hat **keine** `setMinimumSize`-Sperre. User kann das Fenster auf eine Größe ziehen, in der UI-Elemente abgeschnitten oder unbedienbar werden. Außerdem nutzen mehrere Pages fixe Pixel-Größen (`setFixedSize(240, 210)` auf ProfileCard, `setMinimumSize(340, 150)` auf Action-Cards) — bei 720p Display + nicht-maximiertem Fenster überlaufen Layouts.

Phase 11 garantiert **720p-Desktop-Support** (Display 1280×720) und bereitet die Codebasis auf eventuelle Mobile-Phasen vor durch:
- Responsive Layouts mit Breakpoint bei 768px Window-Width
- Touch-Target-Mindestgröße 44×44px (Apple HIG)
- Focus-Ring-Styling für Tastatur+Touch-Navigation
- Wiederverwendbarer `FlowLayout`-Baustein
- Wo Content überlaufen kann: explizite `QScrollArea`-Wraps

**Zielnutzer:** Clemens auf 720p-Display oder mit nicht-maximiertem Fenster. Matthias als Entwickler — sauberes Pattern für künftige Pages.

**Bewusst nicht in Phase 11** *(future work)*:
- Komplett-Mobile-Port (PySide6 → Flutter/React Native) — eigene Major-Phase
- Animations/Transitions zwischen Layout-Modi
- Per-User-Layout-Preferences ("Compact Mode" Setting)
- Dark Mode
- Right-to-left/RTL Support
- Screen-Reader-Integration / volle Accessibility

## 2. Architektur — keine Datenmodell-Änderungen

Phase 11 ist **reine UI-Refactoring-Phase**. Keine Migration, keine neuen Repos, kein Service-Layer. Nur:

- 1 neues Konstanten-Modul `ui/responsive.py`
- 1 neues Widget `widgets/flow_layout.py` (Port von Qt's FlowLayout-Beispiel)
- 1 neues UI-Sub-Widget `widgets/hamburger_menu.py` (Pop-up-Menü für Narrow-Mode)
- Modifikationen an: `app.py`, `pages/menu.py`, `pages/profile_picker.py`, `pages/runner.py`, `pages/import_wizard.py`, `pages/prompt_builder.py`, `pages/review.py`, `widgets/exam_card.py`, `dialogs/profile_manager.py` (im `pages/`-Ordner), `dialogs/event_dialog.py`, `dialogs/assessment_dialog.py`, `style.qss`

## 3. Komponenten

### 3.1 `ui/responsive.py` — Konstanten + Helper

```python
from __future__ import annotations
from PySide6.QtWidgets import QWidget

BREAKPOINT_NARROW = 768   # below this width: narrow-mode layout
MIN_TOUCH_SIZE = 44       # Apple HIG; also feels good for mouse


def is_narrow(widget: QWidget) -> bool:
    """True if the widget's top-level window is below the narrow breakpoint."""
    top = widget.window()
    return top.width() < BREAKPOINT_NARROW
```

Pages, die responsives Verhalten brauchen, importieren `is_narrow` und checken im `resizeEvent`/`reload()`.

### 3.2 `widgets/flow_layout.py` — selbstgeschriebenes FlowLayout

Port von Qt's offiziellem `FlowLayout`-Beispiel (~80 Zeilen Python). Implementiert das `QLayout`-Interface:

```python
class FlowLayout(QLayout):
    def __init__(self, parent=None, margin=0, h_spacing=10, v_spacing=10):
        ...
    def addItem(self, item): ...
    def horizontalSpacing(self) -> int: ...
    def verticalSpacing(self) -> int: ...
    def count(self) -> int: ...
    def itemAt(self, index): ...
    def takeAt(self, index): ...
    def expandingDirections(self) -> Qt.Orientations: ...
    def hasHeightForWidth(self) -> bool: return True
    def heightForWidth(self, width: int) -> int: ...
    def setGeometry(self, rect): ...
    def sizeHint(self) -> QSize: ...
    def minimumSize(self) -> QSize: ...
    def _do_layout(self, rect: QRect, test_only: bool) -> int: ...
```

**Verwendet in**: `pages/profile_picker.py`, `pages/review.py`. Optional zukünftig für History-Grid, Karteikarten-Liste, etc.

### 3.3 `widgets/hamburger_menu.py` — Narrow-Mode Menu-Button

Kleines Helfer-Widget — eine `QPushButton` mit `☰`-Label, die bei Klick ein `QMenu` öffnet:

```python
class HamburgerMenu(QPushButton):
    def __init__(self, parent=None):
        super().__init__("☰", parent)
        self.setObjectName("hamburger")
        self.setFixedSize(MIN_TOUCH_SIZE, MIN_TOUCH_SIZE)
        self._menu = QMenu(self)
        self.setMenu(self._menu)
    
    def add_action(self, label: str, callback) -> None:
        action = self._menu.addAction(label)
        action.triggered.connect(callback)
```

**Verwendet in**: `pages/menu.py` (Top-Bar Narrow-Mode).

### 3.4 App-Level — Minimum Window Size

`src/school_test_engine/app.py`:

```python
window = MainWindow(conn)
window.setMinimumSize(QSize(1024, 600))   # neu — verhindert Schrumpfen
window.resize(QSize(1280, 800))            # default size on first open
```

`1024×600` lässt das Fenster auf 720p-Displays komfortabel passen (auch mit OS-Taskleiste oder anderen Fenstern), während `1280×800` als Default-Größe natural-feeling ist.

### 3.5 MenuPage — Adaptive Top-Bar + Grid

**Aktuell (Wide-Mode bleibt unverändert für ≥ 768px):**
```
[Logo] [Wordmark] ........ [📝 Test bauen] [📅 Termine] [📊 Noten] [Profil]
```

**Narrow-Mode (< 768px):**
```
[Logo] [Wordmark] ........ [☰] [Profil]
```

Die 3 Action-Buttons wandern in das `☰`-Hamburger-Popup als Menü-Einträge "📝 Test bauen", "📅 Termine", "📊 Noten".

**2×2 Action-Grid → 1×4 im Narrow-Mode**: Im Narrow-Mode werden die ÜBEN/AUFGABEN/ANALYSE/RÜCKBLICK-Cards untereinander statt 2 nebeneinander. Implementierung über `QGridLayout` mit dynamischer Spaltenzahl in `resizeEvent`.

**Compact-Mode (Phase-7-pre-existing-Layout)**: bleibt für KA-Hero-Layout — KA-Strip + 4 kompakte Tiles. Im Narrow-Mode werden die 4 Tiles ebenfalls untereinander, KA-Strip behält horizontale Anordnung aber max 2 KAs nebeneinander sichtbar (Scroll horizontal? — siehe Risiko §7).

### 3.6 Profile-Picker — FlowLayout

`pages/profile_picker.py`:
- Entferne `ProfileCard.setFixedSize(240, 210)` → setze stattdessen `setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)` + `setMinimumSize(200, 180)` + `setMaximumWidth(280)`
- Entferne `QGridLayout` mit `COLUMNS = 3`
- Ersetze mit `FlowLayout`
- Cards arrangieren sich: 4-5 nebeneinander auf 1280px-Fenster, 2 auf Tablet (~768px), 1 auf Phone (~480px)

### 3.7 AssessmentDialog — Grade-Selector als 3×2-Grid

Aktuelles `_GradeSelector`:
```
[1] [2] [3] [4] [5] [6]   [,5]
```

Neu:
```
[1] [2] [3]
[4] [5] [6]
       [,5]   ← Half-step toggle in eigener Zeile, rechts ausgerichtet
```

Buttons: 56×56 statt 48×48 (komfortabler Touch-Target). Half-step-Button: 56×40.

Implementierung: `QGridLayout` statt `QHBoxLayout` in `_GradeSelector.__init__`.

### 3.8 Dialog-Breiten lockern

| Dialog | Alt | Neu |
|--------|-----|-----|
| `_ProfileEditDialog` | `setMinimumWidth(540)` | `setMinimumWidth(420)`, `setMaximumWidth(620)` |
| `EventDialog` | `setMinimumWidth(420)` | `setMinimumWidth(380)`, `setMaximumWidth(540)` |
| `AssessmentDialog` | `setMinimumWidth(440)` | `setMinimumWidth(380)`, `setMaximumWidth(540)` |

`setMaximumWidth` verhindert dass Dialoge auf großen Bildschirmen unverhältnismäßig breit werden.

Dialog-Action-Buttons (Save/Cancel/Delete): Verwende `QDialogButtonBox` mit `orientation = Qt.Vertical` wenn Dialog-Width < 400px. Default bleibt Horizontal.

### 3.9 ScrollArea-Wraps

**`pages/prompt_builder.py`**: Form-Bereich + Output-Bereich gemeinsam in einer äußerer `QScrollArea`. Aktuell kann Form-Bereich (Fach+Anzahl+Topics+Verteilung+Stil-Briefing+Kontext) bei Narrow-Window überlaufen.

**`pages/import_wizard.py`**: Page-Content in `QScrollArea` wrappen. Aktuell ist `QTextEdit`-Log scrollbar, aber andere Elemente (Description-Labels, Buttons) können überlaufen.

**`pages/runner.py`**: Frage-Inhalt + Choice-Liste in `QScrollArea` (für lange Mathe-Expressions / mehrzeilige Antwortoptionen). Achtung: Navigation-Buttons (Zurück/Vor/Markieren) müssen **außerhalb** der ScrollArea bleiben, immer sichtbar am unteren Rand.

### 3.10 Touch-Targets ≥ 44px

| Widget | Alt | Neu |
|--------|-----|-----|
| ExamCard `…`-Edit-Button | `setFixedWidth(36)` | `setMinimumWidth(44)`, height 44 |
| AvatarTile | `setFixedSize(56, 56)` | bleibt — schon > 44 |
| Subject-Tab-Buttons in GradesPage | padding 5px 14px (~36 high) | padding 8px 16px (~44 high) |
| HamburgerMenu (neu) | n/a | 44×44 |
| Grade-Selector buttons | 48×48 | 56×56 |

Andere Buttons (Primary, Text, Danger) im QSS prüfen — meiste Standard-`QPushButton` mit padding sind schon ≥ 36 hoch und werden mit QSS-Update (siehe §3.11) auf ≥ 44 gebracht.

### 3.11 Focus-Ring via QSS

Append zu `src/school_test_engine/ui/style.qss`:

```css
/* ----- Phase 11: Focus rings (keyboard + touch navigation) ----- */

QPushButton:focus,
QComboBox:focus,
QLineEdit:focus,
QPlainTextEdit:focus,
QTextEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QRadioButton:focus,
QCheckBox:focus,
QDateEdit:focus {
    outline: none;  /* Qt's default dotted line ist ugly */
    border: 2px solid #3e552d;  /* tea-700 = Kessler accent */
}

/* ClickableCard + ProfileCard fokussierbar machen */
ClickableCard:focus,
QFrame#profileRow:focus,
QFrame#profileCard:focus {
    border: 2px solid #3e552d;
}

/* Hamburger-Button styling */
QPushButton#hamburger {
    background: transparent;
    color: #4a4538;
    border: 1px solid #d8cdb8;
    border-radius: 22px;
    font-size: 18pt;
}
QPushButton#hamburger:hover {
    background: #f4efe6;
}
QPushButton#hamburger:focus {
    border: 2px solid #3e552d;
}

/* Generelle Touch-Target-Höhe für Buttons */
QPushButton {
    min-height: 36px;  /* primary baseline; QSS-overridden objects keep their style */
}
QPushButton#primary,
QPushButton#text,
QPushButton#danger,
QPushButton#topBarAction,
QPushButton#hamburger {
    min-height: 44px;  /* Touch-ready */
}
```

Plus: `setFocusPolicy(Qt.StrongFocus)` programmatisch auf `ClickableCard.__init__` und `_ProfileCard.__init__` setzen — sonst können diese keinen Focus bekommen.

### 3.12 review.py (Phase 2 Review-Page) — FlowLayout

`pages/review.py` hat 4-Spalten-`QGridLayout` für Frage-Status-Cards. Ersetzen mit FlowLayout für responsive Verhalten.

## 4. Tests

**Unit-Tests:**
- `test_responsive.py`: `is_narrow()` mit mock-widget-widths
- `test_flow_layout.py`: FlowLayout-Math (heightForWidth, setGeometry mit verschiedenen widget counts)

**Smoke-Tests (manuell + programmatisch):**
- Jede Page-Konstruktion mit Window-Sizes 800×600, 1024×600, 1280×720, 1920×1080 (programmatisch)
- Hamburger-Menu öffnet sich + Actions feuern korrekt
- FlowLayout arrangiert ProfileCards je nach Fenster-Breite

**Manueller End-to-End:**
- Display in 720p (1280×720) setzen
- Fenster auf 1024×600 verkleinern → alle Seiten bedienbar
- Fenster auf 800×600 verkleinern → Narrow-Mode greift (Hamburger sichtbar, Cards gestackt)
- Tab-Navigation durch eine Page → Focus-Ring sichtbar an aktuellem Widget
- AssessmentDialog öffnen → Grade-Selector 3×2-Grid, alle Buttons gut tappable

## 5. Akzeptanzkriterien

1. `app.py` setzt `setMinimumSize(QSize(1024, 600))` und `resize(QSize(1280, 800))` — Fenster kann nicht kleiner gezogen werden
2. `responsive.py` exportiert `BREAKPOINT_NARROW=768`, `MIN_TOUCH_SIZE=44`, `is_narrow(widget)`
3. `FlowLayout` ist implementiert, instantiierbar, arrangiert Widgets responsive
4. Profile-Picker zeigt ProfileCards in FlowLayout — bei 1280px ≥ 4 nebeneinander, bei 800px ≤ 2 nebeneinander
5. MenuPage bei Window-Width < 768px: HamburgerMenu sichtbar, die 3 Action-Buttons versteckt; Menu-Klick zeigt Popup mit 3 Einträgen
6. MenuPage 2×2-Grid wird zu 1×4 (vertikal) bei Window-Width < 768px
7. AssessmentDialog Grade-Selector zeigt 3×2-Grid mit Buttons ≥ 56×56
8. 3 Pages (prompt_builder, import_wizard, runner) haben `QScrollArea` für Content
9. ExamCard `…`-Button ist ≥ 44×44px
10. Focus-Ring sichtbar wenn Widget via Tab fokussiert wird (manuell verifiziert)
11. Alle 220 bestehenden Tests grün; neue Unit-Tests grün

## 6. Edge Cases

| Fall | Verhalten |
|------|-----------|
| Window resize über die 768px-Grenze hinweg | `resizeEvent` triggert Layout-Switch — Hamburger erscheint/verschwindet, Grid-Cols ändern sich. Keine visible Flackerei dank `setUpdatesEnabled(False)` während Switch. |
| 720p-Display, Fenster auf Vollbild | 1280×720 = Wide-Mode aktiv, alles wie bisher |
| 1024×600 Fenster | Wide-Mode (über 768px), aber Vertikal-Scroll nötig auf einigen Pages — die ScrollArea-Wraps fangen das auf |
| 800×600 Fenster | Narrow-Mode greift, Hamburger erscheint, Grids stacken. Bedienbar. |
| FlowLayout mit nur 1 Widget | Single Widget linksbündig, kein Layout-Bruch |
| Dialog auf Mobile-Width 380px | Dialog-Buttons stacken vertikal via `QDialogButtonBox.Vertical` |
| HamburgerMenu bei sehr klein (< 380px) | Menu-Popup hat Min-Width 200px — passt rechts neben Button oder unter |
| Focus bei dunklem Hintergrund | Border-Farbe `#3e552d` (tea-700) hebt sich gut von paper-Background ab |
| Tab-Order über Pages hinweg | Default Qt Tab-Order — könnte später optimiert werden; reicht für Phase 11 |
| ClickableCard mit `StrongFocus` aber kein Outline | QSS-Selector `ClickableCard:focus` mit `border: 2px solid` greift |

## 7. Risiken

- **Animations-Flackerei beim Resize-Übergang**: schnelles Resize über 768px-Grenze hin und her könnte hässlich aussehen. Mitigation: `widget.setUpdatesEnabled(False)` während Layout-Switch, `setUpdatesEnabled(True)` danach.
- **KA-Strip im Narrow-Mode**: aktuell zeigt KA-Strip bis zu 3 ExamCards nebeneinander. Bei 380px-Window ist EINE Card schon zu breit. Mitigation: Im Narrow-Mode ExamCards mit `setMaximumWidth` constrainen ODER horizontal-scrollbar machen. **Entscheidung in Implementierung**: probieren wir erst Stacking (Cards untereinander im Narrow-Mode). Falls hässlich, horizontal-scroll als Fallback.
- **FlowLayout-Performance**: bei vielen Widgets (z.B. 50 ProfileCards) wird `setGeometry` bei jedem Resize teuer (O(n)). Realistisch werden < 10 Profile da sein — kein Problem. Falls Karteikarten später ihn nutzen mit 200+ Cards: Optimierung später.
- **QSS-`min-height` auf QPushButton global**: könnte Bestand-Buttons zu groß machen. Mitigation: Specifity-Hierarchie via `QPushButton#specific` overrides genau prüfen.
- **Focus-Ring überlappt mit ClickableCard's Drop-Shadow**: bei Drop-Shadow-Cards (Phase 6D) könnten 2 Outlines konkurrieren. Mitigation: Test es im realen Rendering und ggf. Focus-Ring auf ClickableCard mit `border` statt `outline` (das macht Card 4px breiter — nicht ideal, aber okay).
- **Tab-Order möglicherweise verwirrend**: Qt's automatic Tab-Order folgt Widget-Erstellungs-Reihenfolge — meist passt das, aber bei `_dynamic_layout`-rebuilds kann's brechen. Mitigation: erstmal akzeptieren, später `setTabOrder()` falls nötig.
