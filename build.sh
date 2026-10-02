#!/bin/sh
set -eu

cd "$(dirname "$0")"
python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --onefile \
  --name "Chat View" \
  --add-data "index.html:." \
  --add-data "app.css:." \
  --add-data "app.js:." \
  server.py

echo "Built: dist/Chat View"
