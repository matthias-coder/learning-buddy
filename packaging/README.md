# Learning Buddy — Windows Build

## Voraussetzungen (einmalig auf der Windows-Maschine)

1. **Python 3.12** (64-bit) von https://www.python.org — beim Installieren
   „Add Python to PATH" anhaken.
2. **Inno Setup 6** von https://jrsoftware.org/isdl.php — Default-Optionen.
3. **Git** (optional) — falls du das Repo klonen statt USB-kopieren willst.

## Setup (einmalig pro Repo-Checkout)

```powershell
cd C:\pfad\zu\school-test-engine
python -m venv .venv
.venv\Scripts\activate
pip install -e .[build]
```

## Build

```powershell
packaging\build.bat
```

Dauer: ~2-5 Minuten je nach Maschine. Output: `dist\setup_learning-buddy_v1.0.2.exe`
(~80-120 MB single-file Installer).

## Distribution

Den `setup_learning-buddy_vX.Y.Z.exe` per E-Mail, USB-Stick oder Cloud-Share
(WeTransfer, OneDrive, Google Drive) an die Empfänger schicken.

### SmartScreen-Hinweis für Empfänger

> Windows zeigt beim ersten Start eine blaue Warnung
> „Der Computer wurde durch Windows geschützt".
> Klick auf „Weitere Informationen" → „Trotzdem ausführen".
>
> Das Installer ist nicht signiert (Code-Signing-Zertifikat kostet 200-400 €/Jahr,
> nicht sinnvoll für privat). Einmaliger Klick pro Version.

## Was wo landet

| Ort | Inhalt |
|---|---|
| `C:\Program Files\Learning Buddy\` | App-Binary + Qt-DLLs + Assets (alle Windows-User können starten) |
| `%LOCALAPPDATA%\learning-buddy\` | DB + Profile + Avatar-Bilder (pro Windows-User isoliert) |
| Start-Menü → „Learning Buddy" | Start-Verknüpfung + Deinstallation |
| Desktop | Optional (Wizard-Checkbox) |

## Deinstallation

Systemsteuerung → Programme → „Learning Buddy" → Deinstallieren.

User-Daten in `%LOCALAPPDATA%\learning-buddy\` bleiben **erhalten** (für
spätere Re-Installs). Wer Total-Removal will, löscht den Ordner manuell.

## Icon-Refresh (selten nötig)

Wenn sich `assets/logomark.svg` ändert:

```bash
# Auf der Linux/macOS-Dev-Maschine:
pip install cairosvg Pillow
python packaging/prepare_icon.py
git add assets/icon.ico
git commit -m "chore(assets): regenerate icon.ico"
```

## Bekannte Stolpersteine

- **„Python wird nicht gefunden"** — Python-Installer ausgeführt ohne „Add to PATH".
  Neuer Python-Installer mit angehakter PATH-Option installieren.
- **„VC++ Runtime fehlt" beim Start auf Empfänger-PC** — Microsoft Visual C++
  Redistributable 2015-2022 (x64) von Microsoft herunterladen + installieren.
  Wird selten gebraucht (Windows 10/11 hat es meistens schon).
- **First-Run-Antivirus-Scan** — Windows Defender scannt die `.exe` beim
  ersten Start 5-10 Sekunden lang. Gefühlte Startlatenz. Normal.
