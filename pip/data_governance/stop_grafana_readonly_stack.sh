#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Stop the browser-facing proxy first, then the backend, then Grafana itself.
"${ROOT_DIR}/pip/data_governance/stop_nginx_grafana_readonly.sh" || true
pkill -f 'uvicorn main:app' || true
pkill -f 'uvicorn .*main:app' || true

RUN_DIR="${GRAFANA_RUN_DIR:-/tmp/pfe-grafana-readonly}"
PID_FILE="${RUN_DIR}/grafana-server.pid"

if [[ -f "${PID_FILE}" ]]; then
  kill "$(cat "${PID_FILE}")" || true
  rm -f "${PID_FILE}" || true
fi

pkill -f '/usr/sbin/grafana-server --config /etc/grafana/grafana.ini --homepath /usr/share/grafana' || true
# pkill -f 'grafana-server' || true
pkill -f 'grafana server' || true

echo "OK: Grafana read-only stack stopped"
