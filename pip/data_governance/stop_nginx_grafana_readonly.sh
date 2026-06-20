#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONF="${ROOT_DIR}/pip/data_governance/nginx/grafana_readonly.conf"

RUN_DIR="${NGINX_RUN_DIR:-/tmp/nginx-grafana-readonly}"
PID_FILE="${RUN_DIR}/logs/nginx.pid"

if [[ -f "${PID_FILE}" ]]; then
  nginx -p "${RUN_DIR}" -c "${CONF}" -s stop || true
else
  pkill -f 'nginx.*grafana_readonly\.conf' || true
fi
