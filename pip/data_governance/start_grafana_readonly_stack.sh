#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export GRAFANA_PUBLIC_URL="${GRAFANA_PUBLIC_URL:-http://localhost:8081/api/grafana/}"
export GRAFANA_PORT="${GRAFANA_PORT:-3300}"
export GRAFANA_URL="${GRAFANA_URL:-http://127.0.0.1:${GRAFANA_PORT}}"
PYTHON_BIN="${ROOT_DIR}/env/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

# Grafana is exposed through the FastAPI backend and published through Nginx on :8081.
# The browser-facing URL is the Nginx proxy, while the backend still handles auth and
# reverse-proxying to Grafana itself.
"${ROOT_DIR}/scripts/grafana_start_readonly.sh"
"${ROOT_DIR}/pip/data_quality/app/backend/start_api.sh"

if [[ -x "${PYTHON_BIN}" ]]; then
  echo "Synchronizing Grafana with the current PostgreSQL projects..."
  PYTHONPATH="${ROOT_DIR}/pip/data_quality/app/backend:${PYTHONPATH:-}" \
    "${PYTHON_BIN}" "${ROOT_DIR}/scripts/grafana_sync_from_db.py" || \
    echo "⚠️ Grafana sync skipped or failed; Grafana is still started."
else
  echo "⚠️ No usable Python interpreter found; Grafana sync skipped."
fi

"${ROOT_DIR}/pip/data_governance/run_nginx_grafana_readonly.sh"

echo "OK: Grafana service + backend proxy + Nginx (:8081/api/grafana/) started"
