#!/usr/bin/env bash
# Updates LAMZU Configurator on macOS: pulls the latest code and re-runs the installer
# (dependencies, tests and the ~/Applications app bundle).
# Usage: bash scripts/update-mac.sh
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -d .git ]]; then
  echo "Esta pasta não é um clone do git. Desinstale com: bash scripts/uninstall-mac.sh" >&2
  echo "e instale de novo com: git clone https://github.com/henriquelouteiro/LAMZU-TO-MAC.git" >&2
  exit 1
fi

if pgrep -f "lamzu_mac.gui" >/dev/null 2>&1; then
  echo "Feche o LAMZU Configurator antes de atualizar." >&2
  exit 1
fi

echo "==> Baixando a versão mais recente"
git pull --ff-only

bash scripts/install-mac.sh
