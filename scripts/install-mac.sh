#!/usr/bin/env bash
# Installs LAMZU Configurator on macOS:
#   1. creates .venv and installs the package with the GUI (PySide6 + hidapi)
#   2. runs the test suite (no mouse needed)
#   3. creates "~/Applications/LAMZU Configurator.app"
# Usage: bash scripts/install-mac.sh        (PYTHON=/path/to/python3 to override)
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="${PYTHON:-python3}"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "Este script é para macOS." >&2
  exit 1
fi
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "python3 não encontrado. Instale pelo https://www.python.org/downloads/ ou: brew install python" >&2
  exit 1
fi
if ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
  echo "É preciso Python 3.10 ou mais novo (encontrado: $("$PY" --version 2>&1))." >&2
  echo "Instale pelo https://www.python.org/downloads/ ou: brew install python" >&2
  exit 1
fi

echo "==> Criando ambiente Python em .venv"
"$PY" -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -e ".[gui]"

echo "==> Rodando testes (não precisam do mouse)"
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -t .

echo "==> Criando ~/Applications/LAMZU Configurator.app"
APP="$HOME/Applications/LAMZU Configurator.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/MacOS/launcher" <<EOF
#!/bin/bash
exec "$ROOT/.venv/bin/python" -m lamzu_mac.gui "\$@"
EOF
chmod +x "$APP/Contents/MacOS/launcher"

cat > "$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>LAMZU Configurator</string>
  <key>CFBundleDisplayName</key><string>LAMZU Configurator</string>
  <key>CFBundleIdentifier</key><string>local.lamzu-mac.configurator</string>
  <key>CFBundleExecutable</key><string>launcher</string>
  <key>CFBundleIconFile</key><string>app</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
EOF

ICONSET="$(mktemp -d)/app.iconset"
.venv/bin/python -m lamzu_mac.gui.icon --iconset "$ICONSET"
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/app.icns"
rm -rf "$(dirname "$ICONSET")"
touch "$APP"   # make Finder pick up the new icon

cat <<EOF

Pronto.
  Interface:  abra "LAMZU Configurator" em ~/Applications (ou pelo Spotlight)
  Terminal:   source .venv/bin/activate && lamzu selftest
EOF
