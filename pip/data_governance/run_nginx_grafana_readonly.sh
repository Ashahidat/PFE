#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONF="${ROOT_DIR}/pip/data_governance/nginx/grafana_readonly.conf"

RUN_DIR="${NGINX_RUN_DIR:-/tmp/nginx-grafana-readonly}"
mkdir -p "${RUN_DIR}/logs"

PID_FILE="${RUN_DIR}/logs/nginx.pid"
if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" >/dev/null 2>&1; then
  echo "Nginx for Grafana already running."
  exit 0
fi

# Set error_log early (before config parsing) to avoid permission warnings.
exec nginx -p "${RUN_DIR}" -c "${CONF}" -g "error_log ${RUN_DIR}/logs/error.log;"
