#!/usr/bin/env bash
# Removes what scripts/install-mac.sh created: the app bundle in ~/Applications and
# the .venv of this folder. The project folder itself is left for you to delete.
# The mouse keeps its current configuration (it lives in the mouse's memory).
# Usage: bash scripts/uninstall-mac.sh
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
APP="$HOME/Applications/LAMZU Configurator.app"

if pgrep -f "lamzu_mac.gui" >/dev/null 2>&1; then
  echo "Feche o LAMZU Configurator antes de desinstalar." >&2
  exit 1
fi

if [[ -d "$APP" ]]; then
  rm -rf "$APP"
  echo "Removido: $APP"
fi
if [[ -d "$ROOT/.venv" ]]; then
  rm -rf "$ROOT/.venv"
  echo "Removido: $ROOT/.venv"
fi

cat <<EOF

Desinstalado. Para apagar também o código, remova a pasta:
  rm -rf "$ROOT"
EOF
