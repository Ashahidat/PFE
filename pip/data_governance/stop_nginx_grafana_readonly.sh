#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONF="${ROOT_DIR}/pip/data_governance/nginx/grafana_readonly.conf"

RUN_DIR="${NGINX_RUN_DIR:-/tmp/nginx-grafana-readonly}"
PID_FILE="${RUN_DIR}/logs/nginx.pid"

mkdir -p "${RUN_DIR}/logs"

if [[ -f "${PID_FILE}" ]]; then
  kill "$(cat "${PID_FILE}")" || true
fi
pkill -f 'nginx.*grafana_readonly\.conf' || true
