#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/trading-agent}"
cd "$PROJECT_ROOT"

echo "[verify] compile/import"
python3 -m compileall agent >/dev/null

echo "[verify] manifest present"
test -f logs/latest_sync_manifest.json

echo "[verify] health artifact path"
mkdir -p logs memory strategies_config

echo "[verify] env file"
if [[ ! -f ".env" ]]; then
  echo "WARN: .env not found"
fi

echo "[verify] systemd units"
for service in trading-agent trading-dashboard; do
  if command -v systemctl >/dev/null 2>&1; then
    systemctl is-enabled "$service" >/dev/null 2>&1 || true
  fi
done

echo "[verify] done"
