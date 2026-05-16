@echo off
setlocal enabledelayedexpansion

REM Learning Buddy — Windows Build Script
REM Run from the repo root: packaging\build.bat
REM
REM Prerequisites (one-time on the build machine):
REM   - Python 3.12 64-bit (with "Add to PATH" enabled)
REM   - Inno Setup 6  (https://jrsoftware.org/isdl.php)
REM   - This repo cloned, then: python -m venv .venv && .venv\Scripts\pip install -e .[build]

set REPO=%~dp0..
cd /d "%REPO%"

REM ---------------------------------------------------------------------
REM 0. Activate venv if not already active
REM ---------------------------------------------------------------------
if "%VIRTUAL_ENV%"=="" (
    if exist ".venv\Scripts\activate.bat" (
        call ".venv\Scripts\activate.bat"
    ) else (
        echo [error] No active venv and .venv\Scripts\activate.bat not found.
        echo Run: python -m venv .venv ^&^& .venv\Scripts\pip install -e .[build]
        exit /b 1
    )
)

REM ---------------------------------------------------------------------
REM 1. Read __version__ from school_test_engine
REM ---------------------------------------------------------------------
for /f "delims=" %%v in ('python -c "from school_test_engine import __version__; print(__version__)"') do set APPVERSION=%%v
if "%APPVERSION%"=="" (
    echo [error] Could not read __version__ from school_test_engine
    exit /b 1
)
echo [build] App version: %APPVERSION%

REM ---------------------------------------------------------------------
REM 2. PyInstaller — Python-Bundle in dist\learning-buddy\
REM ---------------------------------------------------------------------
echo [build] Running PyInstaller…
python -m PyInstaller packaging\learning-buddy.spec --clean --noconfirm
if errorlevel 1 (
    echo [error] PyInstaller failed
    exit /b 1
)

REM ---------------------------------------------------------------------
REM 3. Inno Setup — single-file installer in dist\
REM ---------------------------------------------------------------------
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
    echo [error] Inno Setup 6 not found at %ISCC%
    echo Install from: https://jrsoftware.org/isdl.php
    exit /b 1
)

echo [build] Running Inno Setup Compiler…
%ISCC% /DMyAppVersion=%APPVERSION% packaging\installer.iss
if errorlevel 1 (
    echo [error] Inno Setup compilation failed
    exit /b 1
)

echo.
echo [done] dist\setup_learning-buddy_v%APPVERSION%.exe
endlocal
