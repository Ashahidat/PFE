#!/usr/bin/env bash
set -euo pipefail

ATLAS_PUBLIC_PORT="${ATLAS_PUBLIC_PORT:-21001}"
ATLAS_INTERNAL_PORT="${ATLAS_INTERNAL_PORT:-21002}"
ATLAS_LEGACY_PORT="${ATLAS_LEGACY_PORT:-21000}"
ATLAS_HOST="${ATLAS_HOST:-127.0.0.1}"
ATLAS_USER="${ATLAS_USER:-admin}"
ATLAS_PASS="${ATLAS_PASS:-admin}"

check_listener() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    echo "== Listener ${ATLAS_HOST}:${port} =="
    ss -ltnp "( sport = :${port} )" 2>/dev/null || true
  else
    echo "== Listener ${ATLAS_HOST}:${port} =="
    echo "ss is not available on this machine."
  fi
}

http_code() {
  local method="$1"
  local url="$2"
  shift 2
  curl -sS -u "${ATLAS_USER}:${ATLAS_PASS}" \
    -o /dev/null \
    -w "%{http_code}" \
    -X "${method}" \
    "$@" \
    "${url}" || true
}

check_http() {
  local port="$1"
  local base_url="http://${ATLAS_HOST}:${port}"
  local version_code write_code

  version_code="$(http_code GET "${base_url}/api/atlas/admin/version")"
  write_code="$(http_code POST "${base_url}/api/atlas/v2/entity" -H 'Content-Type: application/json' -d '{}')"

  echo "== HTTP ${port} =="
  echo "version: ${version_code}"
  echo "write:   ${write_code}"

  if [[ "${port}" == "${ATLAS_PUBLIC_PORT}" ]]; then
    if [[ "${write_code}" == "403" || "${write_code}" == "405" ]]; then
      echo "result: read-only proxy looks enforced"
    else
      echo "result: WARNING - write requests are not blocked on the public port"
    fi
  else
    if [[ "${write_code}" == "403" || "${write_code}" == "405" ]]; then
      echo "result: WARNING - internal port is behaving like the read-only proxy"
    else
      echo "result: internal Atlas is reachable"
    fi
  fi
}

check_listener "${ATLAS_PUBLIC_PORT}"
check_http "${ATLAS_PUBLIC_PORT}"
echo
check_listener "${ATLAS_INTERNAL_PORT}"
check_http "${ATLAS_INTERNAL_PORT}"
echo
check_listener "${ATLAS_LEGACY_PORT}"
legacy_version_code="$(http_code GET "http://${ATLAS_HOST}:${ATLAS_LEGACY_PORT}/api/atlas/admin/version")"
legacy_write_code="$(http_code POST "http://${ATLAS_HOST}:${ATLAS_LEGACY_PORT}/api/atlas/v2/entity" -H 'Content-Type: application/json' -d '{}')"

if [[ "${legacy_version_code}" != "000" || "${legacy_write_code}" != "000" ]]; then
  echo "== HTTP ${ATLAS_LEGACY_PORT} =="
  echo "version: ${legacy_version_code}"
  echo "write:   ${legacy_write_code}"
  echo "result: WARNING - a legacy Atlas endpoint is still reachable on 21000"
else
  echo "== HTTP ${ATLAS_LEGACY_PORT} =="
  echo "version: 000"
  echo "write:   000"
  echo "result: no legacy Atlas listener detected"
fi
