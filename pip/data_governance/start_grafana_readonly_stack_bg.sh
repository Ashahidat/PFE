#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUN_DIR="${GRAFANA_RUN_DIR:-/tmp/pfe-grafana-readonly}"
LOG_FILE="${RUN_DIR}/grafana-start.log"
PID_FILE="${RUN_DIR}/grafana-start.pid"

mkdir -p "${RUN_DIR}"

if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" >/dev/null 2>&1; then
  echo "Grafana stack is already launching/running. Log: ${LOG_FILE}"
  exit 0
fi

rm -f "${PID_FILE}"

nohup bash "${ROOT_DIR}/pip/data_governance/start_grafana_readonly_stack.sh" >"${LOG_FILE}" 2>&1 &
echo $! >"${PID_FILE}"

echo "Grafana stack launched in background."
echo "Log: ${LOG_FILE}"
echo "PID: $(cat "${PID_FILE}")"
