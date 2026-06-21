#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${GRAFANA_PUBLIC_URL:-http://localhost:8000/api/grafana/}"

sudo bash "${ROOT_DIR}/scripts/grafana_fix_reload_loop.sh" --base-url "${BASE_URL}" --no-restart

if command -v curl >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:3000/api/health" >/dev/null 2>&1; then
  echo "Grafana already responds on 127.0.0.1:3000; skipping second start."
  exit 0
fi

if pgrep -f 'grafana-server' >/dev/null 2>&1; then
  echo "Grafana server process already running; skipping second start."
  exit 0
fi

exec sudo /usr/sbin/grafana-server --config /etc/grafana/grafana.ini --homepath /usr/share/grafana
