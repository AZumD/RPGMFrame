#!/usr/bin/env bash
# Build RPGMFrame desktop GUI for Linux aarch64.
# For a native Steam Frame build, run this script on the Frame.
set -euo pipefail
cd "$(dirname "$0")/.."

ARCH="$(uname -m)"
if [[ "$ARCH" != "aarch64" && "$ARCH" != "arm64" ]]; then
  echo "WARNING: building on $ARCH; run on aarch64 for a native Frame binary."
fi

PY=python3
if [[ -x .venv/bin/python ]]; then
  PY=.venv/bin/python
fi

"$PY" -m pip install -e ".[gui,build]"

"$PY" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name RPGMFrame \
  --paths . \
  --hidden-import customtkinter \
  --hidden-import tkinterdnd2 \
  --collect-all customtkinter \
  --collect-all tkinterdnd2 \
  app/main.py

mkdir -p dist/linux-aarch64/RPGMFrame
if [[ -d dist/RPGMFrame ]]; then
  cp -a dist/RPGMFrame/. dist/linux-aarch64/RPGMFrame/
fi

cat > dist/linux-aarch64/RPGMFrame/README.txt <<'EOF'
RPGMFrame (Linux aarch64 / Steam Frame)
=======================================

1. Run: ./RPGMFrame
2. Drop an RPG Maker MV/MZ folder or ZIP
3. Click Convert
4. Unpack the generated *-linux-aarch64.tar.gz
5. Enter the *-frame directory and run ./launch.sh

Needs a graphical desktop/session and Tk.
EOF

chmod +x dist/linux-aarch64/RPGMFrame/RPGMFrame 2>/dev/null || true
echo "Built: dist/linux-aarch64/RPGMFrame/RPGMFrame"
