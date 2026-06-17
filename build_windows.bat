@echo off
:: Build HEIC -> PNG -- executable Windows (PyInstaller)
setlocal EnableDelayedExpansion

echo === Build HEIC ^> PNG --- Windows ===

if not exist ".venv" (
    echo Erreur : venv introuvable. Executez d'abord :
    echo   python -m venv .venv ^&^& .venv\Scripts\activate ^&^& pip install -r requirements.txt
    exit /b 1
)

call .venv\Scripts\activate.bat

python -m pip install --quiet "pyinstaller>=6.0"

if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

python -m PyInstaller ^
    --name=heic2png ^
    --onedir ^
    --windowed ^
    --collect-all=pillow_heif ^
    --collect-all=PIL ^
    --hidden-import=PIL._imaging ^
    main.py

echo.
echo OK  Executable : dist\heic2png\heic2png.exe
echo     Archive    : powershell Compress-Archive -Path dist\heic2png -DestinationPath heic2png-windows.zip
