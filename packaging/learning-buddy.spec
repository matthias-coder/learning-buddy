# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Learning Buddy — Phase 17.5 Windows-Distribution.

Run from the repo root:
    pyinstaller packaging/learning-buddy.spec --clean --noconfirm
Output:
    dist/learning-buddy/learning-buddy.exe + dist/learning-buddy/_internal/*
"""
import os

REPO = os.path.abspath(os.path.join(SPECPATH, ".."))

block_cipher = None


a = Analysis(
    [os.path.join(REPO, "src", "school_test_engine", "__main__.py")],
    pathex=[os.path.join(REPO, "src")],
    binaries=[],
    datas=[
        (os.path.join(REPO, "assets"), "assets"),
        (os.path.join(REPO, "examples", "PROMPT-FOR-AI.md"), "examples"),
        (os.path.join(REPO, "src", "school_test_engine", "storage", "migrations"),
         "school_test_engine/storage/migrations"),
        (os.path.join(REPO, "src", "school_test_engine", "ui", "style.qss"),
         "school_test_engine/ui"),
    ],
    hiddenimports=[
        "icalendar",
        "icalendar.compatibility",
        "icalendar.cal",
        "PySide6.QtSvgWidgets",
        "PySide6.QtPrintSupport",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineCore",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter", "matplotlib", "numpy", "pandas", "scipy",
        "PySide6.QtBluetooth", "PySide6.QtCharts",
        "PySide6.QtDataVisualization", "PySide6.QtMultimedia",
        "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtSensors",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)


pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="learning-buddy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX kann Qt-DLLs zerstören
    console=False,       # GUI-App, kein Terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(REPO, "assets", "icon.ico"),
)


coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="learning-buddy",
)
