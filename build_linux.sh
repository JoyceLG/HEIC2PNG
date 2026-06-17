#!/usr/bin/env bash
# Build HEIC → PNG — exécutable Linux (PyInstaller)
set -e

echo "=== Build HEIC → PNG — Linux ==="

if [ ! -d ".venv" ]; then
    echo "Erreur : venv introuvable. Exécutez d'abord :"
    echo "  python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

source .venv/bin/activate
python -m pip install --quiet "pyinstaller>=6.0"

rm -rf build/ dist/

python -m PyInstaller \
    --name=heic2png \
    --onedir \
    --windowed \
    --collect-all=pillow_heif \
    --collect-all=PIL \
    --hidden-import=PIL._imaging \
    main.py

echo ""
echo "✓ Exécutable : dist/heic2png/heic2png"
echo "  Archive    : tar -czf heic2png-linux.tar.gz -C dist heic2png"
