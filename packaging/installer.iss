; Inno Setup script — Learning Buddy v{#MyAppVersion}
; Compile: ISCC.exe /DMyAppVersion=1.0.2 packaging\installer.iss
;
; Per-machine install (admin), German wizard, opt-in desktop shortcut.

#ifndef MyAppVersion
  #define MyAppVersion "1.0.2"
#endif
#define MyAppName "Learning Buddy"
#define MyAppPublisher "Matthias Keßler"
#define MyAppExeName "learning-buddy.exe"

[Setup]
; AppId — random GUID. NEVER change after first release!
AppId={{8B2E4C7A-5F31-4D8E-9A6B-3C8F7D2E1A95}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppCopyright=© 2026 {#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=setup_learning-buddy_v{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=no

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Verknüpfung auf dem &Desktop erstellen"; \
  GroupDescription: "Zusätzliche Symbole:"; Flags: unchecked

[Files]
Source: "..\dist\learning-buddy\learning-buddy.exe"; \
  DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\learning-buddy\_internal\*"; \
  DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{#MyAppName} deinstallieren"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
  Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{#MyAppName} starten"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Bewusst leer — User-Daten in %LOCALAPPDATA%\learning-buddy\ bleiben erhalten.
