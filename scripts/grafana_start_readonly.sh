#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GRAFANA_PORT="${GRAFANA_PORT:-3300}"
BASE_URL="${GRAFANA_PUBLIC_URL:-http://localhost:8000/api/grafana/}"
RUN_DIR="${GRAFANA_RUN_DIR:-/tmp/pfe-grafana-readonly}"
LOG_FILE="${RUN_DIR}/grafana-server.log"
PID_FILE="${RUN_DIR}/grafana-server.pid"
GRAFANA_BIN="${GRAFANA_BIN:-/usr/sbin/grafana-server}"
GRAFANA_DATA_DIR="${RUN_DIR}/data"
GRAFANA_LOG_DIR="${RUN_DIR}/logs"
GRAFANA_HOME_DIR="/usr/share/grafana"

mkdir -p "${RUN_DIR}" "${GRAFANA_DATA_DIR}" "${GRAFANA_LOG_DIR}"

if command -v curl >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:${GRAFANA_PORT}/api/health" >/dev/null 2>&1; then
  echo "Grafana already responds on 127.0.0.1:${GRAFANA_PORT}; skipping second start."
  exit 0
fi

if [[ -f "${PID_FILE}" ]] && kill -0 "$(cat "${PID_FILE}")" >/dev/null 2>&1; then
  echo "Grafana server process already launching/running; skipping second start."
  exit 0
fi

rm -f "${PID_FILE}"

find "${GRAFANA_DATA_DIR}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

nohup env \
  GF_PATHS_HOME="${GRAFANA_HOME_DIR}" \
  GF_PATHS_DATA="${GRAFANA_DATA_DIR}" \
  GF_PATHS_LOGS="${GRAFANA_LOG_DIR}" \
  GF_SERVER_HTTP_ADDR="127.0.0.1" \
  GF_SERVER_HTTP_PORT="${GRAFANA_PORT}" \
  GF_SERVER_ROOT_URL="${BASE_URL}" \
  GF_SERVER_SERVE_FROM_SUB_PATH="true" \
  GF_SERVER_ENFORCE_DOMAIN="false" \
  GF_AUTH_PROXY_ENABLED="true" \
  GF_AUTH_PROXY_HEADER_NAME="X-WEBAUTH-USER" \
  GF_AUTH_PROXY_HEADER_PROPERTY="username" \
  GF_AUTH_PROXY_AUTO_SIGN_UP="true" \
  GF_AUTH_PROXY_ENABLE_LOGIN_TOKEN="true" \
  GF_AUTH_PROXY_HEADERS="Name:X-WEBAUTH-NAME Role:X-WEBAUTH-ROLE" \
  GF_USERS_DEFAULT_ROLE="Viewer" \
  GF_AUTH_DISABLE_LOGIN_FORM="true" \
  "${GRAFANA_BIN}" --homepath "${GRAFANA_HOME_DIR}" >"${LOG_FILE}" 2>&1 &
echo $! >"${PID_FILE}"

for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${GRAFANA_PORT}/api/health" >/dev/null 2>&1; then
    echo "Grafana started. Log: ${LOG_FILE}"
    echo "PID: $(cat "${PID_FILE}")"
    exit 0
  fi
  sleep 1
done

echo "Grafana start timed out. Log: ${LOG_FILE}" >&2
exit 1
