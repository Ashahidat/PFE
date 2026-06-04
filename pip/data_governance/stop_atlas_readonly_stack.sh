#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ATLAS_HOME="${ROOT_DIR}/pip/data_governance/apache-atlas-2.4.0"
ATLAS_PID_FILE="${ATLAS_HOME}/logs/atlas.pid"
NGINX_RUN_DIR="${NGINX_RUN_DIR:-/tmp/nginx-atlas-readonly}"
NGINX_PID_FILE="${NGINX_RUN_DIR}/logs/nginx.pid"

# Stop UI proxy first, then Atlas.
"${ROOT_DIR}/pip/data_governance/stop_nginx_atlas_readonly.sh" || true

# Fallbacks in case the pid files are stale or a second Atlas/nginx process was
# started outside the helpers.
pkill -f 'nginx.*atlas_readonly\.conf' || true
(cd "${ATLAS_HOME}/bin" && ./atlas_stop.py) || true
pkill -f 'org\.apache\.atlas\.Atlas' || true

rm -f "${NGINX_PID_FILE}" "${ATLAS_PID_FILE}" || true

echo "OK: read-only UI proxy + Atlas stopped"
