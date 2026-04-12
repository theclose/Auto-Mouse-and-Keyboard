@echo off
chcp 65001 >nul
echo ============================================
echo   AutoMacro Build Script v3.0.0
echo ============================================
echo.

:: 1. Run QA check
echo [1/4] Running QA check...
python scripts/qa_check.py --quick
if errorlevel 1 (
    echo.
    echo ❌ QA FAILED! Fix errors before building.
    exit /b 1
)
echo ✅ QA passed
echo.

:: 2. Clean previous build
echo [2/4] Cleaning previous build...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
echo ✅ Cleaned

:: 3. Build
echo.
echo [3/4] Building EXE with PyInstaller...
echo     This may take 2-5 minutes...
pyinstaller autopilot.spec --noconfirm
if errorlevel 1 (
    echo.
    echo ❌ BUILD FAILED!
    exit /b 1
)
echo ✅ Build complete

:: 4. Post-build: create empty dirs for runtime
echo.
echo [4/4] Post-build setup...
if not exist "dist\AutoPilot\logs" mkdir "dist\AutoPilot\logs"
if not exist "dist\AutoPilot\macros" mkdir "dist\AutoPilot\macros"
if not exist "dist\AutoPilot\templates" mkdir "dist\AutoPilot\templates"
if not exist "dist\AutoPilot\screenshots" mkdir "dist\AutoPilot\screenshots"

:: Copy example macro if not already bundled
if not exist "dist\AutoPilot\macros\example.json" (
    if exist "macros\example.json" copy "macros\example.json" "dist\AutoPilot\macros\" >nul
)
echo ✅ Directories created

:: Summary
echo.
echo ============================================
echo   ✅ BUILD SUCCESSFUL
echo   Output: dist\AutoPilot\AutoPilot.exe
echo ============================================
echo.

:: Show size
for %%I in ("dist\AutoPilot\AutoPilot.exe") do echo   EXE size: %%~zI bytes
dir /s "dist\AutoPilot" | findstr "File(s)"
echo.
echo   To run: dist\AutoPilot\AutoPilot.exe
echo ============================================
